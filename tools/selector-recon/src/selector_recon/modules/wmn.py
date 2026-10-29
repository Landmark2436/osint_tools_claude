"""WhatsMyName: username checks driven by the community-maintained wmn-data.json.

The data file is not vendored. It is downloaded from a pinned commit, verified
against a SHA-256 hash and cached. Data: (C) Micah Hoffman and WhatsMyName
contributors, CC BY-SA 4.0, https://github.com/WebBreacher/WhatsMyName
"""

from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from ..http import detect_block
from ..models import Finding, Selector, SelectorType, Status
from ..util import short, site_key
from .base import Module, RunContext

WMN_COMMIT = "35576e909ce4846c769d353f7979d11ac25516b6"
WMN_SHA256 = "b87a3dfdf58d3283657a32e76ee0cd210be369727a9c6f7855485e9de6150e40"
WMN_URL = f"https://raw.githubusercontent.com/WebBreacher/WhatsMyName/{WMN_COMMIT}/wmn-data.json"


def default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return Path(base) / "selector-recon"


def load_wmn_data(ctx: RunContext) -> dict[str, Any]:
    """Load wmn-data.json from --wmn-data, the cache, or the pinned upstream commit (in that order)."""
    override = ctx.options.get("wmn_data")
    if override:
        return json.loads(Path(override).read_text(encoding="utf-8"))
    cache = (ctx.cache_dir or default_cache_dir()) / f"wmn-data-{WMN_COMMIT[:12]}.json"
    if cache.is_file():
        raw = cache.read_bytes()
        if hashlib.sha256(raw).hexdigest() == WMN_SHA256:
            return json.loads(raw)
    resp = ctx.http.get(WMN_URL)
    raw = resp.content
    digest = hashlib.sha256(raw).hexdigest()
    if resp.status != 200 or digest != WMN_SHA256:
        raise RuntimeError(f"could not fetch pinned wmn-data.json (HTTP {resp.status}, sha256 {digest[:12]}…)")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(raw)
    return json.loads(raw)


class WhatsMyName(Module):
    name = "wmn"
    title = "WhatsMyName"
    selector_types = frozenset({SelectorType.USERNAME})
    description = "Checks a username on ~690 sites using the WhatsMyName data file (e_code/e_string vs m_code/m_string)."
    homepage = "https://github.com/WebBreacher/WhatsMyName"
    license = "data CC BY-SA 4.0"
    tos = "Plain GET/POST of public profile pages; each site's own ToS applies. Rate-limited per host."
    can_notify = "no (sites that list profile visitors are rare; none are logged in)"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        data = load_wmn_data(ctx)
        sites = [s for s in data["sites"] if s.get("valid", True)]
        if not ctx.include_nsfw:
            sites = [s for s in sites if "nsfw" not in s.get("cat", "").lower()]
        workers = int(ctx.options.get("workers", 16))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda s: self.check_site(selector, s, ctx), sites))

    def check_site(self, selector: Selector, site: dict[str, Any], ctx: RunContext) -> Finding:
        account = selector.value
        for ch in site.get("strip_bad_char", ""):
            account = account.replace(ch, "")
        url = site["uri_check"].replace("{account}", quote(account, safe="@"))
        pretty = site.get("uri_pretty", site["uri_check"]).replace("{account}", quote(account, safe="@"))
        body = site["post_body"].replace("{account}", account) if site.get("post_body") else None
        # Site headers are kept, except a User-Agent: we always send our own honest one.
        headers = {k: v for k, v in site.get("headers", {}).items() if k.lower() != "user-agent"}
        common = dict(url=pretty, category=site.get("cat"), site_key=site_key(pretty, site["name"]))
        try:
            resp = ctx.http.request(
                "POST" if body is not None else "GET", url, headers=headers, data=body, follow_redirects=False
            )
        except PermissionError as exc:
            return self.finding(selector, site["name"], Status.BLOCKED, evidence=str(exc), **common)
        except httpx.HTTPError as exc:
            return self.finding(selector, site["name"], Status.ERROR, evidence=f"{type(exc).__name__}: {short(str(exc))}", **common)

        if resp.status == site["e_code"] and site["e_string"] in resp.text:
            return self.finding(
                selector, site["name"], Status.FOUND, http_status=resp.status,
                evidence=f"HTTP {resp.status}, page contains {short(site['e_string'], 60)!r}", **common,
            )
        if resp.status == site["m_code"] and site["m_string"] in resp.text:
            return self.finding(
                selector, site["name"], Status.NOT_FOUND, http_status=resp.status,
                evidence=f"HTTP {resp.status}, page contains {short(site['m_string'], 60)!r}", **common,
            )
        reason = detect_block(resp)
        if reason:
            return self.finding(selector, site["name"], Status.BLOCKED, http_status=resp.status, evidence=reason, **common)
        return self.finding(
            selector, site["name"], Status.UNKNOWN, http_status=resp.status,
            evidence=f"HTTP {resp.status}, neither the exists nor the missing pattern matched", **common,
        )
