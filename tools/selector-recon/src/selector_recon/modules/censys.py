"""Censys Platform API: services, ASN, location and DNS names for an IP. Needs CENSYS_API_TOKEN.

Uses the Platform API v3 host lookup with a personal access token (Bearer).
CENSYS_ORG_ID is optional (Free accounts have none). Lookups may consume credits
depending on the plan. The token is never written to outputs.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..models import Finding, Pivot, Selector, SelectorType, Status
from ..util import redact, short
from .base import Module, RunContext


def summarize_host(body: dict[str, Any]) -> dict[str, Any]:
    """Defensive parse of a Platform API host response (fields may move between API versions)."""
    host = body.get("result", body)
    host = host.get("resource", host)
    services = []
    for s in host.get("services") or []:
        services.append({k: s.get(k) for k in ("port", "protocol", "transport_protocol") if s.get(k) is not None})
    asys = host.get("autonomous_system") or {}
    loc = host.get("location") or {}
    dns = host.get("dns") or {}
    names = list(dict.fromkeys([*(dns.get("names") or []), *((dns.get("reverse_dns") or {}).get("names") or [])]))
    return {
        "services": services,
        "asn": asys.get("asn"),
        "as_name": asys.get("name") or asys.get("description"),
        "country": loc.get("country"),
        "city": loc.get("city"),
        "dns_names": names,
    }


class Censys(Module):
    name = "censys"
    title = "Censys"
    selector_types = frozenset({SelectorType.IP})
    needs_key = "CENSYS_API_TOKEN"
    key_required = True
    description = "IP: services, ASN, location and DNS names from the Censys Platform API (needs CENSYS_API_TOKEN)."
    homepage = "https://docs.censys.com/"
    license = "API"
    tos = "Censys ToS; host lookups may consume credits depending on plan."
    can_notify = "no (data comes from Censys's own past scans)"
    api = "https://api.platform.censys.io/v3/global/asset/host/"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        if blocked := self.not_public(selector):
            return blocked
        token = ctx.env(self.needs_key) or ""
        org = ctx.env("CENSYS_ORG_ID")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if org:
            headers["X-Organization-ID"] = org
        page = f"https://platform.censys.io/hosts/{selector.value}"
        try:
            r = ctx.http.get(f"{self.api}{selector.value}", headers=headers)
        except httpx.HTTPError as exc:
            return [self.finding(selector, self.title, Status.ERROR, url=page, evidence=redact(f"{type(exc).__name__}: {short(str(exc))}", token))]
        if r.status == 404:
            return [self.finding(selector, self.title, Status.NOT_FOUND, url=page, http_status=404, evidence="no host record")]
        if r.status in (401, 403):
            return [self.finding(selector, self.title, Status.ERROR, url=page, http_status=r.status,
                                 evidence="token rejected or no API access (check CENSYS_API_TOKEN / CENSYS_ORG_ID)")]
        if r.status == 429:
            return [self.finding(selector, self.title, Status.BLOCKED, url=page, http_status=429, evidence="rate limited")]
        if r.status != 200:
            return [self.finding(selector, self.title, Status.UNKNOWN, url=page, http_status=r.status, evidence=f"HTTP {r.status}")]
        try:
            s = summarize_host(json.loads(r.text))
        except (ValueError, AttributeError):
            return [self.finding(selector, self.title, Status.UNKNOWN, url=page, http_status=200, evidence="unexpected response format")]
        ports = ", ".join(f"{x.get('port')}/{x.get('protocol', '?')}" for x in s["services"]) or "none"
        bits = [f"services {ports}"]
        if s["asn"]:
            bits.append(f"AS{s['asn']} {s['as_name'] or ''}".strip())
        if s["country"]:
            bits.append(", ".join(x for x in (s["city"], s["country"]) if x))
        if s["dns_names"]:
            bits.append("names " + ", ".join(s["dns_names"][:5]))
        pivots = [Pivot(SelectorType.DOMAIN, n, "DNS name seen by Censys") for n in s["dns_names"][:25]]
        return [self.finding(selector, self.title, Status.FOUND, url=page, http_status=200, data=s, pivots=pivots,
                             evidence=short("; ".join(bits), 300))]
