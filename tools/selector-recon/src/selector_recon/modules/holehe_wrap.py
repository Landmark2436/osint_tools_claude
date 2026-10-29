"""holehe (megadose/holehe, GPL-3.0), restricted to reviewed passive checks. Opt-in: --modules +holehe

holehe is an optional extra and is never vendored. Of its ~120 checks, only the
four below are run. Each was read line by line; none touches a sign-up, login or
password-reset flow:

- protonmail: public PGP key server lookup (api.protonmail.ch/pks)
- gravatar:   public profile JSON by MD5 hash (legacy endpoint)
- duolingo:   public user search API by email
- office365:  Microsoft Autodiscover lookup. holehe hardcodes an Outlook client
              User-Agent for it, so it only runs with --browser-ua.

Excluded on review: rambler (labelled "register" upstream; queries the
registration page's account-info RPC), and every other module (register,
login or password-recovery methods).
"""

from __future__ import annotations

import asyncio
import importlib
from typing import Any

from ..models import Finding, Selector, SelectorType, Status
from ..util import site_key
from .base import Module, RunContext

REVIEWED = {
    "protonmail": "holehe.modules.mails.protonmail",
    "gravatar": "holehe.modules.cms.gravatar",
    "duolingo": "holehe.modules.learning.duolingo",
    "office365": "holehe.modules.software.office365",
}
NEEDS_CLIENT_UA = {"office365"}
# Match holehe results to the same site in selector-recon's own modules (for cross-checks).
SITE_KEYS = {"protonmail": "proton.me", "gravatar": "gravatar.com"}


class Holehe(Module):
    name = "holehe"
    title = "holehe"
    selector_types = frozenset({SelectorType.EMAIL})
    default_enabled = False
    requires = ("holehe",)
    install_hint = "pip install '.[holehe]' (GPL-3.0)"
    description = "Opt-in. Four reviewed passive holehe checks: protonmail, gravatar, duolingo, office365."
    homepage = "https://github.com/megadose/holehe"
    license = "GPL-3.0 (optional extra, not vendored)"
    tos = "Public lookup endpoints only; sign-up, login and password-reset checks are never run."
    can_notify = "no (only reviewed passive checks run)"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        from ..http import BROWSER_USER_AGENT

        names = [n for n in REVIEWED if n not in NEEDS_CLIENT_UA or ctx.user_agent == BROWSER_USER_AGENT]
        results = asyncio.run(self._run_all(selector.value, names, ctx))
        out = [self.to_finding(selector, r) for r in results]
        for n in REVIEWED:
            if n not in names:
                out.append(self.finding(selector, f"holehe: {n}", Status.UNKNOWN,
                                        evidence="skipped: sends a client User-Agent; run with --browser-ua to include"))
        return out

    async def _run_all(self, email: str, names: list[str], ctx: RunContext) -> list[dict[str, Any]]:
        import httpx

        out: list[dict[str, Any]] = []
        async with httpx.AsyncClient(headers={"User-Agent": ctx.user_agent}, timeout=ctx.timeout) as client:
            for n in names:
                func = getattr(importlib.import_module(REVIEWED[n]), n)
                try:
                    await func(email, client, out)
                except Exception as exc:  # holehe modules raise on unexpected responses
                    out.append({"name": n, "domain": None, "error": f"{type(exc).__name__}: {exc}"})
        return out

    def to_finding(self, selector: Selector, r: dict[str, Any]) -> Finding:
        source = f"holehe: {r.get('name')}"
        domain = r.get("domain")
        url = f"https://{domain}/" if domain else None
        key = SITE_KEYS.get(r.get("name", "")) or (site_key(url, r.get("name", "")) if url else None)
        common = dict(url=url, site_key=key)
        if r.get("error"):
            return self.finding(selector, source, Status.ERROR, evidence=str(r["error"])[:200], **common)
        if r.get("rateLimit"):
            return self.finding(selector, source, Status.BLOCKED, evidence="holehe reports rate limit or unexpected answer", **common)
        others = r.get("others") or {}
        if r.get("exists"):
            extra = "; " + ", ".join(f"{k}: {v}" for k, v in others.items()) if others else ""
            return self.finding(selector, source, Status.FOUND, evidence=f"account exists per holehe ({domain}){extra}",
                                data={k: str(v) for k, v in others.items()}, **common)
        return self.finding(selector, source, Status.NOT_FOUND, evidence=f"no account per holehe ({domain})", **common)
