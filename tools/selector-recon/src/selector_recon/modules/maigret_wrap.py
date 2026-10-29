"""Maigret (soxoj/maigret, MIT) as a library, normalized to Findings.

Restrictions compared to plain Maigret, to stay inside selector-recon's rules:
- sites marked `tls_fingerprint` are skipped (Maigret would impersonate a browser TLS fingerprint),
- the Cloudflare bypass stays off, no cookies, no Tor/I2P,
- every request carries selector-recon's honest User-Agent instead of a random or fake browser one,
- no recursive search: usernames and links found on profiles become pivot hints only.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from ..http import USER_AGENT
from ..models import Finding, Pivot, Selector, SelectorType, Status
from ..util import short, site_key
from .base import Module, RunContext

_ID_TYPES = {"username": SelectorType.USERNAME, "email": SelectorType.EMAIL}
# Maigret CheckError types that mean "a protection stopped us", reported as blocked.
_BLOCK_ERRORS = {"Captcha", "Bot protection", "Access denied", "Rate limited", "Login required", "Censorship", "Request blocked"}


class _SilentNotify:
    """Maigret calls start/update/finish/warning/... on its notifier; ignore all of it."""

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: None


class Maigret(Module):
    name = "maigret"
    title = "Maigret"
    selector_types = frozenset({SelectorType.USERNAME})
    requires = ("maigret",)
    install_hint = "pip install '.[maigret]'"
    description = "Runs Maigret's top-ranked sites (default 500) via its Python API; extracts profile IDs as pivots."
    homepage = "https://github.com/soxoj/maigret"
    license = "MIT"
    tos = "Plain GET of public profile pages; each site's own ToS applies. Impersonation and bypass features disabled."
    can_notify = "no"

    def load_sites(self, ctx: RunContext) -> tuple[dict[str, Any], int]:
        import maigret
        from maigret.sites import MaigretDatabase

        path = ctx.options.get("maigret_data") or str(Path(maigret.__file__).parent / "resources" / "data.json")
        db = MaigretDatabase().load_from_path(path)
        excluded = [] if ctx.include_nsfw else ["nsfw"]
        sites = db.ranked_sites_dict(top=int(ctx.options.get("maigret_top", 500)), excluded_tags=excluded, disabled=False)
        kept, skipped = {}, 0
        for name, site in sites.items():
            if "tls_fingerprint" in (site.protection or []):
                skipped += 1
                continue
            site.headers = {k: v for k, v in (site.headers or {}).items() if k.lower() != "user-agent"}
            site.headers["User-Agent"] = USER_AGENT
            kept[name] = site
        return kept, skipped

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        from maigret.checking import maigret as maigret_search

        sites, skipped = self.load_sites(ctx)
        logger = logging.getLogger("selector_recon.maigret")
        logger.setLevel(logging.CRITICAL)
        results = asyncio.run(
            maigret_search(
                selector.value,
                sites,
                logger,
                query_notify=_SilentNotify(),
                proxy=os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None,
                timeout=ctx.timeout,
                is_parsing_enabled=True,
                no_progressbar=True,
                max_connections=int(ctx.options.get("workers", 16)),
                cloudflare_bypass=None,
                dns_resolver="threaded",
            )
        )
        findings = [self.to_finding(selector, name, res) for name, res in results.items()]
        if skipped:
            findings.append(self.finding(
                selector, "Maigret (skipped sites)", Status.UNKNOWN,
                evidence=f"{skipped} site(s) skipped: they need browser TLS impersonation, which selector-recon does not use",
            ))
        return findings

    def to_finding(self, selector: Selector, name: str, res: dict[str, Any]) -> Finding:
        """Map one entry of Maigret's result dict to a Finding."""
        check = res["status"]
        status_name = getattr(check.status, "name", str(check.status))
        site = res.get("site")
        url = res.get("url_user") or getattr(check, "site_url_user", None) or None
        http_status = res.get("http_status") if isinstance(res.get("http_status"), int) else None
        check_type = getattr(site, "check_type", "?")
        common = dict(
            url=url,
            http_status=http_status,
            category=", ".join(getattr(check, "tags", None) or getattr(site, "tags", []) or []) or None,
            site_key=site_key(url or getattr(site, "url_main", None), name),
        )
        if status_name == "CLAIMED":
            data = {k: str(v) for k, v in (check.ids_data or {}).items()}
            pivots = self.pivots(res, data)
            evidence = f"HTTP {http_status}, detected via {check_type}"
            if data:
                evidence += "; profile fields: " + short(", ".join(f"{k}={v}" for k, v in list(data.items())[:6]), 160)
            return self.finding(selector, name, Status.FOUND, evidence=evidence, data=data, pivots=pivots, **common)
        if status_name == "AVAILABLE":
            return self.finding(selector, name, Status.NOT_FOUND, evidence=f"HTTP {http_status}, not detected via {check_type}", **common)
        if status_name == "ILLEGAL":
            return self.finding(selector, name, Status.NOT_FOUND, evidence="username format not allowed on this site", **common)
        error = getattr(check, "error", None)
        text = short(str(error)) if error else "inconclusive"
        if error is not None and getattr(error, "type", None) in _BLOCK_ERRORS:
            return self.finding(selector, name, Status.BLOCKED, evidence=text, **common)
        return self.finding(selector, name, Status.UNKNOWN, evidence=text, **common)

    def pivots(self, res: dict[str, Any], data: dict[str, str]) -> list[Pivot]:
        out: list[Pivot] = []
        for value, id_type in (res.get("ids_usernames") or {}).items():
            if id_type in _ID_TYPES:
                out.append(Pivot(_ID_TYPES[id_type], str(value), f"{id_type} in profile data"))
        if "email" in data and "@" in data["email"]:
            out.append(Pivot(SelectorType.EMAIL, data["email"], "email in profile data"))
        return out
