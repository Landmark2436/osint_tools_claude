"""Manual lookup links for phone numbers. Nothing is fetched; the links go into the manual-check list."""

from __future__ import annotations

from urllib.parse import quote

from ..models import Confidence, Finding, Selector, SelectorType, Status
from .base import Module, RunContext
from .phone_info import analyze


def links_for(a: dict) -> list[tuple[str, str, str]]:
    """(source, url, note) for an analyzed number."""
    e164, national, intl = a["e164"], a["national"], a["international"]
    digits = e164.lstrip("+")
    query = " OR ".join(f'"{v}"' for v in dict.fromkeys([e164, intl, national]))
    links = [
        ("Google search", f"https://www.google.com/search?q={quote(query)}", "exact-match search for common formats"),
        ("DuckDuckGo search", f"https://duckduckgo.com/?q={quote(query)}", "exact-match search for common formats"),
        ("Bing search", f"https://www.bing.com/search?q={quote(query)}", "exact-match search for common formats"),
        ("WhatsApp", f"https://wa.me/{digits}", "opens a chat page; sending nothing notifies nobody"),
        ("Telegram", f"https://t.me/+{digits}", "resolves only if the owner allows lookup by number"),
    ]
    if a.get("region"):
        links.append(("Truecaller", f"https://www.truecaller.com/search/{a['region'].lower()}/{a['national_number']}",
                      "needs a Truecaller login; their ToS apply"))
    return links


class PhoneLinks(Module):
    name = "phone_links"
    title = "Phone lookup links"
    selector_types = frozenset({SelectorType.PHONE})
    needs_network = False
    description = "Builds manual lookup links (search engines, WhatsApp, Telegram, Truecaller). Opens nothing."
    homepage = ""
    license = "own code"
    tos = "Links only; you open them yourself."
    can_notify = "no (links are not opened; do not message the number)"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        try:
            a = analyze(selector.value, ctx.options.get("region"))
        except ValueError:
            return []
        return [
            self.finding(selector, source, Status.UNKNOWN, url=url, manual=True, confidence=Confidence.LOW,
                         evidence=f"manual lookup link, not opened by selector-recon; {note}", flags=["link only"])
            for source, url, note in links_for(a)
        ]
