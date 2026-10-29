"""Gravatar: avatar and public profile looked up by the SHA-256 hash of the address."""

from __future__ import annotations

import hashlib
import json
from urllib.parse import urlsplit

import httpx

from ..models import Finding, Pivot, Selector, SelectorType, Status
from ..util import short
from .base import Module, RunContext


def gravatar_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _username_from_url(url: str) -> str | None:
    path = [p for p in urlsplit(url).path.split("/") if p]
    if len(path) == 1 and 1 < len(path[0]) <= 40 and path[0].lstrip("@"):
        return path[0].lstrip("@")
    return None


class Gravatar(Module):
    name = "gravatar"
    title = "Gravatar"
    selector_types = frozenset({SelectorType.EMAIL})
    needs_key = "GRAVATAR_API_KEY"
    description = "Avatar and public profile (name, location, linked accounts) by SHA-256 hash of the address."
    homepage = "https://docs.gravatar.com/"
    license = "API"
    tos = "Public profile API; optional API key raises the rate limit. Gravatar ToS apply."
    profile_pages = True
    can_notify = "no"
    avatar_base = "https://gravatar.com/avatar/"
    api_base = "https://api.gravatar.com/v3/profiles/"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        h = gravatar_hash(selector.value)
        return [self.avatar(selector, h, ctx), self.profile(selector, h, ctx)]

    def avatar(self, selector: Selector, h: str, ctx: RunContext) -> Finding:
        url = f"{self.avatar_base}{h}?d=404&s=200"
        try:
            r = ctx.http.get(url)
        except httpx.HTTPError as exc:
            return self.finding(selector, "Gravatar avatar", Status.ERROR, url=url, evidence=f"{type(exc).__name__}: {short(str(exc))}")
        if r.status == 200:
            return self.finding(selector, "Gravatar avatar", Status.FOUND, url=url, http_status=200,
                                evidence=f"avatar image exists (hash {h[:12]}…)", site_key="gravatar.com")
        if r.status == 404:
            return self.finding(selector, "Gravatar avatar", Status.NOT_FOUND, url=url, http_status=404,
                                evidence="no avatar for this hash", site_key="gravatar.com")
        return self.finding(selector, "Gravatar avatar", Status.UNKNOWN, url=url, http_status=r.status, evidence=f"HTTP {r.status}")

    def profile(self, selector: Selector, h: str, ctx: RunContext) -> Finding:
        url = f"{self.api_base}{h}"
        key = ctx.env(self.needs_key)
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        try:
            r = ctx.http.get(url, headers=headers)
        except httpx.HTTPError as exc:
            return self.finding(selector, "Gravatar profile", Status.ERROR, url=url, evidence=f"{type(exc).__name__}: {short(str(exc))}")
        if r.status == 404:
            return self.finding(selector, "Gravatar profile", Status.NOT_FOUND, http_status=404, url=url,
                                evidence="no public profile", site_key="gravatar.com")
        if r.status == 429:
            return self.finding(selector, "Gravatar profile", Status.BLOCKED, http_status=429, url=url,
                                evidence="rate limited; set GRAVATAR_API_KEY or retry later")
        if r.status != 200:
            return self.finding(selector, "Gravatar profile", Status.UNKNOWN, http_status=r.status, url=url, evidence=f"HTTP {r.status}")
        try:
            p = json.loads(r.text)
        except ValueError:
            return self.finding(selector, "Gravatar profile", Status.UNKNOWN, http_status=200, url=url, evidence="response is not JSON")
        fields = {k: p.get(k) for k in ("display_name", "profile_url", "location", "job_title", "company", "pronouns", "description")}
        fields = {k: str(v) for k, v in fields.items() if v}
        accounts = [a for a in p.get("verified_accounts") or [] if not a.get("is_hidden")]
        pivots = []
        slug = _username_from_url(fields.get("profile_url", ""))
        if slug:
            pivots.append(Pivot(SelectorType.USERNAME, slug, "Gravatar profile name"))
        for a in accounts:
            name = _username_from_url(a.get("url", ""))
            if name:
                pivots.append(Pivot(SelectorType.USERNAME, name, f"verified {a.get('service_label') or a.get('service_type')} account on Gravatar"))
        evidence = ", ".join(f"{k}={v}" for k, v in fields.items() if k != "description")
        if accounts:
            evidence += "; verified accounts: " + ", ".join(a.get("url", "") for a in accounts)
        data = {**fields, "verified_accounts": [{k: a.get(k) for k in ("service_label", "url")} for a in accounts]}
        return self.finding(selector, "Gravatar profile", Status.FOUND, http_status=200,
                            url=fields.get("profile_url") or url, evidence=short(evidence or "profile exists", 300),
                            data=data, pivots=pivots, site_key="gravatar.com")
