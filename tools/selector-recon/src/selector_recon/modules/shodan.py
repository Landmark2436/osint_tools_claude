"""Shodan: open ports, hostnames and known CVEs for an IP; subdomains for a domain (with key).

Without SHODAN_API_KEY the free InternetDB endpoint is used. With a key, the full
host API is used (no query credits). API keys are never written to outputs.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..models import Finding, Pivot, Selector, SelectorType, Status
from ..util import redact, short
from .base import Module, RunContext

MAX_PIVOTS = 25


def _host_pivots(hostnames: list[str], domains: list[str]) -> list[Pivot]:
    seen = dict.fromkeys([*domains, *hostnames])
    return [Pivot(SelectorType.DOMAIN, h, "hostname seen by Shodan") for h in list(seen)[:MAX_PIVOTS]]


class Shodan(Module):
    name = "shodan"
    title = "Shodan"
    selector_types = frozenset({SelectorType.IP})
    needs_key = "SHODAN_API_KEY"
    description = "IP: open ports, hostnames, CPEs, CVEs. Free InternetDB without a key, full host API with SHODAN_API_KEY."
    homepage = "https://www.shodan.io/"
    license = "API; InternetDB free for non-commercial use"
    tos = "Shodan ToS; InternetDB is free for non-commercial use. Host lookups use no query credits."
    can_notify = "no (data comes from Shodan's own past scans)"
    internetdb = "https://internetdb.shodan.io/"
    api = "https://api.shodan.io/"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        if blocked := self.not_public(selector):
            return blocked
        key = ctx.env(self.needs_key)
        page = f"https://www.shodan.io/host/{selector.value}"
        if key:
            url, source = f"{self.api}shodan/host/{selector.value}?key={key}&minify=true", "Shodan host API"
        else:
            url, source = f"{self.internetdb}{selector.value}", "Shodan InternetDB"
        try:
            r = ctx.http.get(url)
        except httpx.HTTPError as exc:
            return [self.finding(selector, source, Status.ERROR, url=page, evidence=redact(f"{type(exc).__name__}: {short(str(exc))}", key))]
        if r.status == 404:
            return [self.finding(selector, source, Status.NOT_FOUND, url=page, http_status=404, evidence="no information for this IP")]
        if r.status in (401, 403):
            return [self.finding(selector, source, Status.ERROR, url=page, http_status=r.status, evidence="API key rejected (check SHODAN_API_KEY)")]
        if r.status == 429:
            return [self.finding(selector, source, Status.BLOCKED, url=page, http_status=429, evidence="rate limited")]
        if r.status != 200:
            return [self.finding(selector, source, Status.UNKNOWN, url=page, http_status=r.status, evidence=f"HTTP {r.status}")]
        try:
            d: dict[str, Any] = json.loads(r.text)
        except ValueError:
            return [self.finding(selector, source, Status.UNKNOWN, url=page, http_status=200, evidence="response is not JSON")]
        vulns = d.get("vulns") or []
        if isinstance(vulns, dict):
            vulns = list(vulns)
        data = {
            "ports": sorted(d.get("ports") or []),
            "hostnames": d.get("hostnames") or [],
            "domains": d.get("domains") or [],
            "cpes": d.get("cpes") or [],
            "tags": d.get("tags") or [],
            "vulns": sorted(vulns),
        }
        for k in ("org", "isp", "asn", "country_name", "city", "os", "last_update"):
            if d.get(k):
                data[k] = d[k]
        bits = [f"ports {', '.join(map(str, data['ports'])) or 'none'}"]
        if data["hostnames"]:
            bits.append("hostnames " + ", ".join(data["hostnames"][:5]))
        for k in ("org", "asn", "country_name", "last_update"):
            if data.get(k):
                bits.append(f"{k.replace('_name', '')} {data[k]}")
        if data["tags"]:
            bits.append("tags " + ", ".join(data["tags"]))
        if data["vulns"]:
            bits.append(f"{len(data['vulns'])} CVE(s) listed")
        return [self.finding(selector, source, Status.FOUND, url=page, http_status=200, data=data,
                             evidence=short("; ".join(bits), 300), pivots=_host_pivots(data["hostnames"], data["domains"]))]


class ShodanDns(Module):
    name = "shodan_dns"
    title = "Shodan DNS"
    selector_types = frozenset({SelectorType.DOMAIN})
    needs_key = "SHODAN_API_KEY"
    key_required = True
    default_enabled = False
    description = "Opt-in, needs SHODAN_API_KEY, costs 1 query credit: subdomains and DNS records Shodan knows for a domain."
    homepage = "https://developer.shodan.io/api"
    license = "API"
    tos = "Shodan ToS; each lookup uses one query credit."
    can_notify = "no"
    api = "https://api.shodan.io/"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        key = ctx.env(self.needs_key) or ""
        page = f"https://www.shodan.io/domain/{selector.value}"
        try:
            r = ctx.http.get(f"{self.api}dns/domain/{selector.value}?key={key}")
        except httpx.HTTPError as exc:
            return [self.finding(selector, self.title, Status.ERROR, url=page, evidence=redact(f"{type(exc).__name__}: {short(str(exc))}", key))]
        if r.status == 404:
            return [self.finding(selector, self.title, Status.NOT_FOUND, url=page, http_status=404, evidence="no DNS data")]
        if r.status != 200:
            status = Status.BLOCKED if r.status == 429 else Status.ERROR
            return [self.finding(selector, self.title, status, url=page, http_status=r.status, evidence=f"HTTP {r.status}")]
        try:
            d = json.loads(r.text)
        except ValueError:
            return [self.finding(selector, self.title, Status.UNKNOWN, url=page, http_status=200, evidence="response is not JSON")]
        subs = sorted({f"{s}.{selector.value}" for s in d.get("subdomains") or [] if s})
        records = [{k: e.get(k) for k in ("subdomain", "type", "value", "last_seen")} for e in d.get("data") or []]
        pivots = [Pivot(SelectorType.DOMAIN, s, "subdomain known to Shodan") for s in subs[:MAX_PIVOTS]]
        return [self.finding(selector, self.title, Status.FOUND, url=page, http_status=200, pivots=pivots,
                             data={"subdomains": subs, "records": records[:500], "tags": d.get("tags") or []},
                             evidence=f"{len(subs)} subdomain(s), {len(records)} DNS record(s)")]
