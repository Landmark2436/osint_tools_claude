"""RDAP (the successor of WHOIS) for domains and IP networks, via the rdap.org bootstrap redirector."""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..models import Finding, Pivot, Selector, SelectorType, Status
from ..util import registrable_domain, short
from .base import Module, RunContext


def _vcard_name(entity: dict[str, Any]) -> str | None:
    for item in (entity.get("vcardArray") or [None, []])[1]:
        if isinstance(item, list) and len(item) >= 4 and item[0] in ("fn", "org") and item[3]:
            return str(item[3])
    return None


def summarize(obj: dict[str, Any]) -> dict[str, Any]:
    """Pick the fields worth citing from an RDAP domain or ip network object."""
    events = {e.get("eventAction"): e.get("eventDate") for e in obj.get("events", []) if e.get("eventAction")}
    entities = {}
    for ent in obj.get("entities", []):
        name = _vcard_name(ent) or ent.get("handle")
        for role in ent.get("roles", []):
            if name and role not in entities:
                entities[role] = name
    out = {
        "handle": obj.get("handle"),
        "name": obj.get("ldhName") or obj.get("name"),
        "status": obj.get("status", []),
        "events": events,
        "entities": entities,
        "nameservers": [ns.get("ldhName", "").lower() for ns in obj.get("nameservers", []) if ns.get("ldhName")],
    }
    if obj.get("objectClassName") == "ip network":
        out.update(range=f"{obj.get('startAddress')} - {obj.get('endAddress')}", country=obj.get("country"),
                   type=obj.get("type"), parent=obj.get("parentHandle"))
    return {k: v for k, v in out.items() if v}


class Rdap(Module):
    name = "rdap"
    title = "RDAP"
    selector_types = frozenset({SelectorType.DOMAIN, SelectorType.IP})
    description = "Registration data (registrar, dates, status, network owner, range) via RDAP."
    homepage = "https://about.rdap.org/"
    license = "registry data, terms per registry"
    tos = "Public RDAP servers; registries limit query rates."
    can_notify = "no"
    base = "https://rdap.org/"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        if blocked := self.not_public(selector):
            return blocked
        if selector.type is SelectorType.DOMAIN:
            target = registrable_domain(selector.value)
            url = f"{self.base}domain/{target}"
            manual = f"https://lookup.icann.org/en/lookup?name={target}"
        else:
            target = selector.value
            url = f"{self.base}ip/{target}"
            manual = f"https://search.arin.net/rdap/?query={target}"
        try:
            r = ctx.http.get(url, headers={"Accept": "application/rdap+json"})
        except httpx.HTTPError as exc:
            return [self.finding(selector, "RDAP", Status.ERROR, url=manual, manual=True, evidence=f"{type(exc).__name__}: {short(str(exc))}")]
        if r.status == 404:
            return [self.finding(selector, "RDAP", Status.NOT_FOUND, url=manual, http_status=404, manual=True,
                                 evidence=f"no RDAP record for {target} (not registered, or the registry has no RDAP; check WHOIS)")]
        if r.status == 429:
            return [self.finding(selector, "RDAP", Status.BLOCKED, url=manual, http_status=429, evidence="rate limited by the registry")]
        if r.status != 200:
            return [self.finding(selector, "RDAP", Status.UNKNOWN, url=manual, http_status=r.status, manual=True, evidence=f"HTTP {r.status}")]
        try:
            s = summarize(json.loads(r.text))
        except ValueError:
            return [self.finding(selector, "RDAP", Status.UNKNOWN, url=r.url, http_status=200, evidence="response is not JSON")]
        bits = []
        if s.get("entities", {}).get("registrar"):
            bits.append(f"registrar {s['entities']['registrar']}")
        if s.get("entities", {}).get("registrant"):
            bits.append(f"registrant {s['entities']['registrant']}")
        for action in ("registration", "expiration", "last changed"):
            if s.get("events", {}).get(action):
                bits.append(f"{action} {s['events'][action][:10]}")
        if s.get("range"):
            bits.append(f"network {s.get('name', '')} {s['range']} {s.get('country', '')}".strip())
        if s.get("status"):
            bits.append("status " + ", ".join(s["status"]))
        pivots = []
        if selector.type is SelectorType.DOMAIN and target != selector.value:
            pivots.append(Pivot(SelectorType.DOMAIN, target, "registrable domain"))
        return [self.finding(selector, "RDAP", Status.FOUND, url=r.url, http_status=200, data=s, pivots=pivots,
                             evidence=short("; ".join(bits) or "record exists", 300))]
