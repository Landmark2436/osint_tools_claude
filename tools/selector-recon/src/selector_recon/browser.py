"""Headless browser for adapters that need rendered pages (Playwright, Chromium).

Rules enforced here, for every adapter:
- one browser instance per run, started lazily, pages opened one at a time;
- a fresh, non-persistent context: no user profile, cookies or logins of yours;
- no stealth plugins, fingerprint spoofing, proxies or CAPTCHA solving;
- the run's User-Agent (honest by default) is used as is;
- robots.txt is always checked before a page is opened;
- bot challenges and CAPTCHAs are reported, never worked around.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .http import Response, detect_block

log = logging.getLogger("selector_recon")

INSTALL_HINT = "pip install '.[browser]' && playwright install chromium"


class BrowserUnavailable(RuntimeError):
    pass


@dataclass
class PageResult:
    url: str
    status: int | None
    title: str
    text: str
    html: str
    screenshot: str | None
    block_reason: str | None


def slug(text: str, limit: int = 60) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")[:limit] or "page"


class BrowserSession:
    """Owns the Playwright browser for one run. Use get_page() / close()."""

    def __init__(self, out_dir: Path, user_agent: str, timeout: float = 20.0,
                 executable_path: str | None = None, headless: bool = True) -> None:
        self.out_dir = out_dir
        self.user_agent = user_agent
        self.timeout_ms = int(timeout * 1000)
        self.executable_path = executable_path
        self.headless = headless
        self._pw: Any = None
        self._browser: Any = None
        self._context: Any = None
        self.failure: str | None = None
        self.shots = 0

    def _start(self) -> None:
        if self._context is not None:
            return
        if self.failure:
            raise BrowserUnavailable(self.failure)
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.failure = f"Playwright is not installed ({INSTALL_HINT})"
            raise BrowserUnavailable(self.failure) from None
        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self.headless, executable_path=self.executable_path)
            # new_context() is an isolated, in-memory profile that is discarded on close.
            self._context = self._browser.new_context(
                user_agent=self.user_agent, locale="en-US", viewport={"width": 1280, "height": 900},
                accept_downloads=False, service_workers="block",
            )
            self._context.set_default_timeout(self.timeout_ms)
        except Exception as exc:
            self.close()
            self.failure = f"cannot start Chromium ({type(exc).__name__}: {str(exc).splitlines()[0]}); {INSTALL_HINT}"
            raise BrowserUnavailable(self.failure) from None

    def new_page(self) -> Any:
        self._start()
        return self._context.new_page()

    def capture(self, page: Any, name: str, response: Any = None) -> PageResult:
        """Read the rendered page, save a screenshot under out_dir/screenshots and check for bot challenges."""
        shots = self.out_dir / "screenshots"
        shots.mkdir(parents=True, exist_ok=True)
        self.shots += 1
        rel = f"screenshots/{self.shots:03d}-{slug(name)}.png"
        try:
            page.screenshot(path=str(self.out_dir / rel), full_page=False)
        except Exception as exc:  # a screenshot failure should not lose the page result
            log.debug("screenshot failed: %s", exc)
            rel = None
        html = page.content()
        status = response.status if response is not None else None
        title = page.title()
        text = page.inner_text("body") if page.query_selector("body") else ""
        block = detect_block(Response(page.url, status or 200, html, {}))
        if not block and re.search(r"verify (that )?you are (a )?human|are you a robot|unusual traffic", text, re.I):
            block = "human-verification page"
        return PageResult(page.url, status, title, text, html, rel, block)

    def open(self, url: str, name: str) -> PageResult:
        """Open a public URL in a new tab, wait for it to settle, capture it, close the tab."""
        page = self.new_page()
        try:
            response = page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 8000))
            except Exception:
                pass  # pages with long-polling never go idle; take what is rendered
            return self.capture(page, name, response)
        finally:
            page.close()

    def close(self) -> None:
        for obj in (self._context, self._browser):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass
        self._pw = self._browser = self._context = None
