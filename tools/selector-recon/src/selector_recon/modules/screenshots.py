"""Browser adapter: screenshot every found profile page as evidence. Opt-in.

Runs after the other modules for a selector and attaches the screenshot to the
existing finding instead of adding rows. Pages that turn out to be a 404 or a
bot challenge in a real browser are flagged, which helps spot false positives.
"""

from __future__ import annotations

from ..models import Finding, Selector, SelectorType, Status
from ..modules import all_modules
from .base import BrowserModule, RunContext


class Screenshots(BrowserModule):
    name = "screenshots"
    title = "Screenshots"
    selector_types = frozenset({SelectorType.USERNAME, SelectorType.EMAIL})
    default_enabled = False
    run_last = True
    description = "Opt-in browser adapter: saves a screenshot of each found profile page (max --max-screenshots)."
    license = "own code"
    tos = "Opens only pages other modules already found, one at a time; robots.txt respected."
    can_notify = "no (a profile view without login; sites that list visitors are rare)"

    def candidates(self, ctx: RunContext) -> list[Finding]:
        mods = all_modules()
        seen, out = set(), []
        for f in ctx.findings:
            m = mods.get(f.module)
            if (f.status is Status.FOUND and f.url and f.url.startswith(("http://", "https://")) and not f.manual
                    and not f.screenshot and m is not None and m.profile_pages and f.url not in seen):
                seen.add(f.url)
                out.append(f)
        return out

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        limit = int(ctx.options.get("max_screenshots", 30))
        todo = self.candidates(ctx)
        saved = blocked = skipped = 0
        for f in todo[:limit]:
            result = self.open_page(selector, ctx, f.url, f.source)
            if isinstance(result, Finding):  # robots.txt
                f.flags.append("no screenshot: robots.txt disallows")
                skipped += 1
                continue
            same_url = [g for g in ctx.findings if g.url == f.url]
            for g in same_url:
                g.screenshot = result.screenshot
                if result.block_reason:
                    g.flags.append(f"screenshot shows {result.block_reason}")
                elif result.status and result.status >= 400:
                    g.flags.append(f"page returned HTTP {result.status} in the browser: possible false positive")
            saved += result.screenshot is not None
            blocked += bool(result.block_reason)
        rest = max(len(todo) - limit, 0)
        ctx.note = f"{saved} screenshot(s), {blocked} showing a bot challenge, {skipped} skipped by robots.txt" + (
            f", {rest} over the limit" if rest else "")
        return []
