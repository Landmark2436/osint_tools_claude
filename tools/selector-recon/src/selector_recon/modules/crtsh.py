"""crt.sh certificate transparency search: hostnames seen in certificates for a domain."""

from __future__ import annotations

import json
from urllib.parse import quote

import httpx

from ..models import Finding, Pivot, Selector, SelectorType, Status
from ..util import short
from .base import Module, RunContext

MAX_PIVOTS = 25


def hostnames(entries: list[dict], domain: str) -> list[str]:
    names = set()
    for e in entries:
        for n in str(e.get("name_value", "")).splitlines():
            n = n.strip().lower().removeprefix("*.")
            if n == domain or n.endswith("." + domain):
                names.add(n)
    return sorted(names)


class CrtSh(Module):
    name = "crtsh"
    title = "crt.sh"
    selector_types = frozenset({SelectorType.DOMAIN})
    description = "Certificate transparency logs: subdomains (as pivots), first and latest certificate."
    homepage = "https://crt.sh/"
    license = "data from public CT logs"
    tos = "Free community service by Sectigo; slow and often overloaded, so one query per domain with a long timeout."
    can_notify = "no"
    base = "https://crt.sh/"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        d = selector.value
        api = f"{self.base}?q={quote('%.' + d)}&output=json"
        page = f"{self.base}?q={quote('%.' + d)}"
        try:
            r = ctx.http.get(api, timeout=max(ctx.timeout, 30.0))
        except httpx.HTTPError as exc:
            return [self.finding(selector, self.title, Status.ERROR, url=page, manual=True,
                                 evidence=f"{type(exc).__name__}: {short(str(exc))} (crt.sh is often overloaded; open it yourself)")]
        if r.status != 200:
            status = Status.BLOCKED if r.status == 429 else Status.ERROR
            return [self.finding(selector, self.title, status, url=page, http_status=r.status, manual=True,
                                 evidence=f"HTTP {r.status} (crt.sh is often overloaded; open it yourself)")]
        try:
            entries = json.loads(r.text) if r.text.strip() else []
        except ValueError:
            return [self.finding(selector, self.title, Status.UNKNOWN, url=page, http_status=200, manual=True, evidence="response is not JSON")]
        if not entries:
            return [self.finding(selector, self.title, Status.NOT_FOUND, url=page, http_status=200, evidence="no certificates logged")]
        names = hostnames(entries, d)
        dates = sorted(str(e.get("not_before", ""))[:10] for e in entries if e.get("not_before"))
        subs = [n for n in names if n != d]
        pivots = [Pivot(SelectorType.DOMAIN, n, "hostname in a certificate") for n in subs[:MAX_PIVOTS]]
        ev = f"{len(entries)} certificate(s), {len(names)} hostname(s); first {dates[0] if dates else '?'}, latest {dates[-1] if dates else '?'}"
        if len(subs) > MAX_PIVOTS:
            ev += f"; first {MAX_PIVOTS} of {len(subs)} subdomains listed as pivots"
        return [self.finding(selector, self.title, Status.FOUND, url=page, http_status=200, evidence=ev,
                             data={"hostnames": names[:500], "certificates": len(entries)}, pivots=pivots)]
