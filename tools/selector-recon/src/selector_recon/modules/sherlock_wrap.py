"""Sherlock (sherlock-project, MIT) as a library, normalized to Findings.

Uses the site list bundled with the installed sherlock-project version, so
results are reproducible for a pinned version. Sherlock's built-in Firefox
User-Agent is replaced by selector-recon's through per-site headers (the honest
tool string by default, a fixed browser string only with --browser-ua).
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
from typing import Any

from ..models import Finding, Selector, SelectorType, Status
from ..util import short, site_key
from .base import Module, RunContext


class Sherlock(Module):
    name = "sherlock"
    title = "Sherlock"
    selector_types = frozenset({SelectorType.USERNAME})
    requires = ("sherlock_project",)
    install_hint = "pip install '.[sherlock]'"
    description = "Runs the Sherlock site list (~480 sites) via its Python API."
    homepage = "https://github.com/sherlock-project/sherlock"
    license = "MIT"
    tos = "Plain GET of public profile pages; each site's own ToS applies."
    profile_pages = True
    can_notify = "no"

    def load_sites(self, ctx: RunContext) -> dict[str, dict[str, Any]]:
        import sherlock_project
        from sherlock_project.sites import SitesInformation

        path = ctx.options.get("sherlock_data") or str(Path(sherlock_project.__file__).parent / "resources" / "data.json")
        # SitesInformation prints a warning to stdout when the upstream exclusion list is unreachable.
        with contextlib.redirect_stdout(io.StringIO()):
            sites = SitesInformation(data_file_path=path, honor_exclusions=ctx.options.get("sherlock_exclusions", True))
        if not ctx.include_nsfw:
            sites.remove_nsfw_sites()
        data = {}
        for site in sites:
            info = dict(site.information)
            info["headers"] = {**info.get("headers", {}), "User-Agent": ctx.user_agent}
            data[site.name] = info
        return data

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        from sherlock_project.notify import QueryNotify
        from sherlock_project.sherlock import sherlock

        site_data = self.load_sites(ctx)
        results = sherlock(selector.value, site_data, QueryNotify(), timeout=int(max(ctx.timeout, 1)))
        return [self.to_finding(selector, name, res, site_data.get(name, {})) for name, res in results.items()]

    def to_finding(self, selector: Selector, name: str, res: dict[str, Any], info: dict[str, Any]) -> Finding:
        """Map one entry of sherlock()'s result dict to a Finding."""
        status_name = getattr(res["status"].status, "name", str(res["status"].status))
        url = res.get("url_user") or None
        http_status = res.get("http_status") if isinstance(res.get("http_status"), int) else None
        context = getattr(res["status"], "context", None)
        method = info.get("errorType", "?")
        if isinstance(method, list):
            method = "+".join(method)
        common = dict(url=url, http_status=http_status, site_key=site_key(url or info.get("urlMain"), name))
        if status_name == "CLAIMED":
            return self.finding(selector, name, Status.FOUND, evidence=f"HTTP {http_status}, detected via {method}", **common)
        if status_name == "AVAILABLE":
            return self.finding(selector, name, Status.NOT_FOUND, evidence=f"HTTP {http_status}, not detected via {method}", **common)
        if status_name == "ILLEGAL":
            return self.finding(selector, name, Status.NOT_FOUND, evidence="username format not allowed on this site", **common)
        if status_name == "WAF":
            return self.finding(selector, name, Status.BLOCKED, evidence="request blocked by WAF", **common)
        return self.finding(selector, name, Status.UNKNOWN, evidence=short(context or f"HTTP {http_status}, inconclusive"), **common)
