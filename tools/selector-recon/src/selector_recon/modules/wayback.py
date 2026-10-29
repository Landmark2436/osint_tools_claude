"""Internet Archive Wayback Machine: first and latest capture of a domain."""

from __future__ import annotations

import json
from urllib.parse import quote

import httpx

from ..models import Finding, Selector, SelectorType, Status
from ..util import short
from .base import Module, RunContext


def _ts(ts: str) -> str:
    return f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}" if len(ts) >= 8 else ts


class Wayback(Module):
    name = "wayback"
    title = "Wayback Machine"
    selector_types = frozenset({SelectorType.DOMAIN})
    description = "First and latest archived capture of the domain (CDX API)."
    homepage = "https://archive.org/developers/wayback-cdx-server.html"
    license = "archive.org terms"
    tos = "Public CDX API; two small queries per domain."
    can_notify = "no"
    base = "https://web.archive.org/"

    def _cdx(self, ctx: RunContext, domain: str, limit: int) -> list[list[str]]:
        url = (f"{self.base}cdx/search/cdx?url={quote(domain)}&matchType=domain&output=json"
               f"&fl=timestamp,original,statuscode&limit={limit}")
        r = ctx.http.get(url, timeout=max(ctx.timeout, 20.0))
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}")
        rows = json.loads(r.text) if r.text.strip() else []
        return rows[1:] if rows and rows[0] and rows[0][0] == "timestamp" else rows

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        d = selector.value
        page = f"{self.base}web/*/{d}*"
        try:
            first = self._cdx(ctx, d, 1)
            last = self._cdx(ctx, d, -1) if first else []
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            return [self.finding(selector, self.title, Status.ERROR, url=page, manual=True, evidence=f"{type(exc).__name__}: {short(str(exc))}")]
        if not first:
            return [self.finding(selector, self.title, Status.NOT_FOUND, url=page, evidence="no captures")]
        f, l = first[0], (last[-1] if last else first[0])
        data = {"first": {"timestamp": f[0], "url": f[1]}, "latest": {"timestamp": l[0], "url": l[1]}}
        return [self.finding(selector, self.title, Status.FOUND, url=f"{self.base}web/{f[0]}/{f[1]}", data=data,
                             evidence=f"first capture {_ts(f[0])} ({f[1]}), latest {_ts(l[0])}")]
