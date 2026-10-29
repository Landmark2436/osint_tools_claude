"""Module interface. One source = one subclass of Module in its own file."""

from __future__ import annotations

import importlib.util
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from ..models import Confidence, Finding, Selector, SelectorType, Status

if TYPE_CHECKING:
    from ..dnsutil import DnsClient
    from ..http import HttpClient

log = logging.getLogger("selector_recon")


@dataclass
class RunContext:
    """Everything a module may use during a run. Modules get no other global state."""

    http: HttpClient
    out_dir: Path
    dns: DnsClient | None = None
    timeout: float = 10.0
    include_nsfw: bool = True
    cache_dir: Path | None = None
    options: dict[str, Any] = field(default_factory=dict)
    browser: Any = None  # BrowserSession, set by the runner; started only when a browser module runs
    findings: list[Finding] = field(default_factory=list)  # earlier findings for the current selector
    note: str = ""  # one-line summary a module may leave for the module table; the runner clears it

    @property
    def user_agent(self) -> str:
        return self.http.user_agent

    def env(self, name: str) -> str | None:
        value = os.environ.get(name, "").strip()
        return value or None


class Module:
    name: ClassVar[str]
    title: ClassVar[str]
    selector_types: ClassVar[frozenset[SelectorType]]
    needs_network: ClassVar[bool] = True
    needs_browser: ClassVar[bool] = False
    needs_key: ClassVar[str | None] = None  # env var name; without it the module runs in reduced mode or is skipped
    key_required: ClassVar[bool] = False  # True: skip entirely without the key
    default_enabled: ClassVar[bool] = True
    requires: ClassVar[tuple[str, ...]] = ()  # importable packages from optional extras
    install_hint: ClassVar[str] = ""
    # Documentation, rendered into the README module table and `--list-modules`.
    description: ClassVar[str] = ""
    homepage: ClassVar[str] = ""
    license: ClassVar[str] = ""
    tos: ClassVar[str] = ""
    can_notify: ClassVar[str] = "no"
    profile_pages: ClassVar[bool] = False  # its found URLs are profile pages worth a screenshot
    run_last: ClassVar[bool] = False  # browser post-processing that needs the other modules' results

    def unavailable_reason(self, ctx: RunContext | None = None) -> str | None:
        """Why this module cannot run right now, or None if it can."""
        missing = [pkg for pkg in self.requires if importlib.util.find_spec(pkg) is None]
        if missing:
            return f"missing package(s) {', '.join(missing)}" + (f"; {self.install_hint}" if self.install_hint else "")
        if self.key_required and self.needs_key and not os.environ.get(self.needs_key, "").strip():
            return f"needs API key in ${self.needs_key}"
        return None

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        raise NotImplementedError

    def not_public(self, selector: Selector) -> list[Finding] | None:
        """For IP selectors: a single finding if the address is not globally routable, else None."""
        import ipaddress

        if selector.type is SelectorType.IP and not ipaddress.ip_address(selector.value).is_global:
            return [self.finding(selector, self.title, Status.NOT_FOUND, confidence=Confidence.HIGH,
                                 evidence="not a public address; no lookup made")]
        return None

    # Helpers so modules build findings consistently.
    def finding(self, selector: Selector, source: str, status: Status, **kwargs: Any) -> Finding:
        kwargs.setdefault("confidence", Confidence.LOW if status in (Status.UNKNOWN, Status.ERROR) else Confidence.MEDIUM)
        return Finding(
            selector=selector.value,
            selector_type=selector.type,
            module=self.name,
            source=source,
            status=status,
            **kwargs,
        )


class BrowserModule(Module):
    """Base for adapters that need a rendered page. Skipped cleanly when no browser is available."""

    needs_browser = True
    requires = ("playwright",)
    install_hint = "pip install '.[browser]' && playwright install chromium"

    def open_page(self, selector: Selector, ctx: RunContext, url: str, source: str):
        """Open url after a robots.txt check. Returns a PageResult, or a Finding if the page may not be opened."""
        if not ctx.http.robots_allowed(url):
            return self.finding(selector, source, Status.UNKNOWN, url=url, manual=True,
                                evidence="robots.txt disallows automated access: open it yourself")
        return ctx.browser.open(url, f"{self.name}-{source}")
