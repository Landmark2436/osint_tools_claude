"""Browser adapter: the Have I Been Pwned website search, for use without an API key. Opt-in.

Opens the public start page, types the address into its search field, reads the
rendered answer and saves a screenshot. A bot challenge (HIBP uses Cloudflare
Turnstile) is reported as blocked and goes to the manual-check list; it is never
solved or bypassed. Skipped when HIBP_API_KEY is set, because the API module
already has the answer.
"""

from __future__ import annotations

import re

from ..browser import PageResult
from ..models import Confidence, Finding, Selector, SelectorType, Status
from ..util import short
from .base import BrowserModule, RunContext

SITE = "https://haveibeenpwned.com/"
INPUTS = ('input[type="email"]', "#emailInput", "#Account", 'input[name="Account"]', 'input[type="search"]', 'input[type="text"]')
NOT_PWNED = re.compile(r"good news|no pwnage|not been pwned|wasn.t found in any", re.I)
PWNED = re.compile(r"oh no|pwned in \d+|found in \d+ (data )?breach|\d+ data breach", re.I)


def classify(text: str) -> tuple[Status, str]:
    """Map the rendered result text to a status and a short evidence line."""
    if NOT_PWNED.search(text):
        return Status.NOT_FOUND, "website: no breach found"
    m = PWNED.search(text)
    if m:
        count = re.search(r"(\d+)\s+(data )?breach", text, re.I)
        return Status.FOUND, f"website: pwned{f' in {count.group(1)} breach(es)' if count else ''}"
    return Status.UNKNOWN, "website answer not recognized"


class HibpWeb(BrowserModule):
    name = "hibp_web"
    title = "HIBP website"
    selector_types = frozenset({SelectorType.EMAIL})
    default_enabled = False
    description = "Opt-in browser adapter: HIBP website search with screenshot; blocked on bot challenges."
    homepage = SITE
    license = "website"
    tos = "Public search page; HIBP offers the API for automated use, so prefer the hibp module with a key."
    can_notify = "no"
    site = SITE

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        if ctx.env("HIBP_API_KEY"):
            ctx.note = "skipped: HIBP_API_KEY is set, the hibp module covers this"
            return []
        page = ctx.browser.new_page()  # raises BrowserUnavailable before any request is made
        try:
            if not ctx.http.robots_allowed(self.site):
                return [self.finding(selector, self.title, Status.UNKNOWN, url=self.site, manual=True,
                                     evidence="robots.txt disallows automated access: search it yourself")]
            response = page.goto(self.site, wait_until="domcontentloaded")
            first = ctx.browser.capture(page, "hibp-start", response)
            if first.block_reason:
                return [self._blocked(selector, first)]
            field = next((page.query_selector(s) for s in INPUTS if page.query_selector(s)), None)
            if field is None:
                return [self.finding(selector, self.title, Status.UNKNOWN, url=self.site, manual=True,
                                     screenshot=first.screenshot, evidence="search field not found (page layout changed?)")]
            field.fill(selector.value)
            field.press("Enter")
            try:
                page.wait_for_function(
                    "() => /good news|no pwnage|oh no|pwned in|breach/i.test(document.body.innerText)", timeout=15000)
            except Exception:
                pass
            result = ctx.browser.capture(page, "hibp-result")
        finally:
            page.close()
        if result.block_reason:
            return [self._blocked(selector, result)]
        status, evidence = classify(result.text)
        return [self.finding(selector, self.title, status, url=self.site, screenshot=result.screenshot,
                             manual=status is Status.UNKNOWN, confidence=Confidence.MEDIUM if status is not Status.UNKNOWN else Confidence.LOW,
                             evidence=evidence, site_key="haveibeenpwned.com", data={"page_text": short(result.text, 400)})]

    def _blocked(self, selector: Selector, page: PageResult) -> Finding:
        return self.finding(selector, self.title, Status.BLOCKED, url=self.site, screenshot=page.screenshot,
                            evidence=f"{page.block_reason}: not bypassed, search it yourself")
