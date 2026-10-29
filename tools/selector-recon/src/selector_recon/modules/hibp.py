"""Have I Been Pwned: breach metadata for an email address.

Metadata only (breach name, date, data classes). Pastes are not queried: they
point to dumped content. Without HIBP_API_KEY the module adds a manual-check link.
"""

from __future__ import annotations

import json
from urllib.parse import quote

import httpx

from ..models import Finding, Selector, SelectorType, Status
from ..util import redact, short
from .base import Module, RunContext

API = "https://haveibeenpwned.com/api/v3/breachedaccount/"
SITE = "https://haveibeenpwned.com/"


class Hibp(Module):
    name = "hibp"
    title = "Have I Been Pwned"
    selector_types = frozenset({SelectorType.EMAIL})
    needs_key = "HIBP_API_KEY"
    description = "Breach metadata (name, date, data classes) via the HIBP v3 API; manual link without a key."
    homepage = "https://haveibeenpwned.com/API/v3"
    license = "API (attribution required)"
    tos = "Paid API key; rate limit per plan (selector-recon waits 6.5 s between calls). Attribute HIBP when citing."
    can_notify = "no"
    api = API

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        key = ctx.env(self.needs_key)
        if not key:
            return [self.finding(selector, self.title, Status.UNKNOWN, url=SITE, manual=True,
                                 evidence="no HIBP_API_KEY set: search the address on the website yourself")]
        ctx.http.set_host_interval("haveibeenpwned.com", float(ctx.options.get("hibp_interval", 6.5)))
        url = f"{self.api}{quote(selector.value, safe='@')}?truncateResponse=false"
        try:
            r = ctx.http.get(url, headers={"hibp-api-key": key})
        except httpx.HTTPError as exc:
            return [self.finding(selector, self.title, Status.ERROR, url=SITE, evidence=redact(f"{type(exc).__name__}: {short(str(exc))}", key))]
        if r.status == 404:
            return [self.finding(selector, self.title, Status.NOT_FOUND, url=SITE, http_status=404,
                                 evidence="address not in any breach loaded into HIBP")]
        if r.status in (401, 403):
            return [self.finding(selector, self.title, Status.ERROR, url=SITE, http_status=r.status,
                                 evidence="API key rejected (check HIBP_API_KEY and subscription)")]
        if r.status == 429:
            return [self.finding(selector, self.title, Status.BLOCKED, url=SITE, http_status=429,
                                 evidence=f"rate limited (retry-after {r.headers.get('retry-after', '?')} s)")]
        if r.status != 200:
            return [self.finding(selector, self.title, Status.UNKNOWN, url=SITE, http_status=r.status, evidence=f"HTTP {r.status}")]
        try:
            breaches = json.loads(r.text)
        except ValueError:
            return [self.finding(selector, self.title, Status.UNKNOWN, url=SITE, http_status=200, evidence="response is not JSON")]
        out = []
        for b in breaches:
            data = {
                "name": b.get("Name"),
                "title": b.get("Title"),
                "domain": b.get("Domain"),
                "breach_date": b.get("BreachDate"),
                "added_date": b.get("AddedDate"),
                "pwn_count": b.get("PwnCount"),
                "data_classes": b.get("DataClasses") or [],
                "is_verified": b.get("IsVerified"),
                "is_sensitive": b.get("IsSensitive"),
            }
            flags = [f for f, on in (("unverified breach", data["is_verified"] is False),
                                     ("sensitive breach", data["is_sensitive"])) if on]
            out.append(self.finding(
                selector, f"HIBP: {data['title'] or data['name']}", Status.FOUND, http_status=200,
                url=f"{SITE}PwnedWebsites#{data['name']}", data=data, flags=flags,
                evidence=short(f"breach {data['breach_date']} ({data['domain'] or 'no domain'}); data: {', '.join(data['data_classes'])}", 240),
            ))
        return out or [self.finding(selector, self.title, Status.NOT_FOUND, url=SITE, http_status=200, evidence="empty breach list")]
