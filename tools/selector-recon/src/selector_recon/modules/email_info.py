"""Offline email analysis: syntax, provider-specific normalization, free-mail/disposable flags, pivots."""

from __future__ import annotations

import re

from ..detect import looks_like_domain
from ..models import Confidence, Finding, Pivot, Selector, SelectorType, Status
from ..util import data_list
from .base import Module, RunContext

# dot-atom local part (RFC 5322 without quoted strings and comments)
_LOCAL_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$")

# Providers that deliver user+tag@domain to user@domain.
_PLUS_ADDRESSING = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com", "proton.me", "protonmail.com", "protonmail.ch", "pm.me",
    "fastmail.com", "fastmail.fm", "posteo.de", "mailbox.org", "zoho.com", "yandex.com", "yandex.ru",
}
# Providers that ignore dots in the local part.
_DOTS_IGNORED = {"gmail.com", "googlemail.com"}
_ALIASES = {"googlemail.com": "gmail.com"}
# RFC 2606 / RFC 6761 names that never belong to a real mailbox owner.
_RESERVED = ("example.com", "example.net", "example.org")
_RESERVED_TLDS = ("test", "example", "invalid", "localhost")


def analyze(address: str) -> dict:
    """Split, validate and normalize an email address. Pure function, no I/O."""
    local, _, domain = address.rpartition("@")
    domain = domain.lower().rstrip(".")
    problems = []
    if not local or not domain:
        problems.append("missing local part or domain")
    if len(local) > 64:
        problems.append("local part longer than 64 characters")
    if len(address) > 254:
        problems.append("address longer than 254 characters")
    if local and not _LOCAL_RE.match(local):
        problems.append("local part has characters or dots not allowed unquoted")
    if domain and not looks_like_domain(domain):
        problems.append(f"domain {domain!r} is not a valid hostname with a known TLD")

    base_local, tag = local, None
    canonical_domain = _ALIASES.get(domain, domain)
    if "+" in local and (domain in _PLUS_ADDRESSING or canonical_domain in _PLUS_ADDRESSING):
        base_local, _, tag = local.partition("+")
    if canonical_domain in _DOTS_IGNORED:
        base_local = base_local.replace(".", "")
    canonical = f"{base_local.lower()}@{canonical_domain}" if local and domain else address.lower()
    return {
        "local": local,
        "domain": domain,
        "valid": not problems,
        "problems": problems,
        "canonical": canonical,
        "subaddress_tag": tag,
        "possible_tag": tag is None and "+" in local,
        "freemail": domain in data_list("freemail_domains.txt"),
        "disposable": domain in data_list("disposable_domains.txt"),
        "reserved": domain in _RESERVED or any(domain.endswith("." + r) for r in _RESERVED)
        or domain.rsplit(".", 1)[-1] in _RESERVED_TLDS,
    }


class EmailInfo(Module):
    name = "email_info"
    title = "Email syntax"
    selector_types = frozenset({SelectorType.EMAIL})
    needs_network = False
    description = "Offline: syntax check, provider-specific normalization (+tags, Gmail dots), free-mail/disposable flags."
    homepage = "https://github.com/disposable-email-domains/disposable-email-domains"
    license = "own code; disposable list CC0"
    tos = "No network access."
    can_notify = "no"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        a = analyze(selector.value)
        if not a["valid"]:
            return [self.finding(selector, self.title, Status.NOT_FOUND, confidence=Confidence.HIGH,
                                 evidence="invalid address: " + "; ".join(a["problems"]), data=a)]
        parts = ["valid syntax"]
        flags = []
        if a["canonical"] != selector.value.lower():
            parts.append(f"canonical form {a['canonical']}")
        if a["subaddress_tag"]:
            parts.append(f"subaddress tag '+{a['subaddress_tag']}'")
        elif a["possible_tag"]:
            parts.append("'+' in local part may be a subaddress tag (provider support unknown)")
        if a["freemail"]:
            flags.append("free-mail provider")
        if a["disposable"]:
            flags.append("disposable-address domain")
        if a["reserved"]:
            flags.append("reserved example domain (RFC 2606): not a real mailbox")

        pivots = []
        user = a["canonical"].split("@")[0]
        pivots.append(Pivot(SelectorType.USERNAME, user, "local part of the email address"))
        if a["local"].lower() != user and "+" not in a["local"]:
            pivots.append(Pivot(SelectorType.USERNAME, a["local"], "local part as written"))
        if not a["freemail"] and not a["disposable"]:
            pivots.append(Pivot(SelectorType.DOMAIN, a["domain"], "email domain (not a free-mail provider)"))
        return [self.finding(selector, self.title, Status.FOUND, confidence=Confidence.HIGH,
                             evidence="; ".join(parts), data=a, flags=flags, pivots=pivots)]
