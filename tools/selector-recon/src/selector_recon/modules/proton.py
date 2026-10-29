"""Proton Mail public key server: does a Proton-hosted address exist, and when was its key created?"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from ..models import Finding, Selector, SelectorType, Status
from ..util import short
from .base import Module, RunContext

_PUB_RE = re.compile(r"^pub:([0-9A-Fa-f]+):(\d+):(\d*):(\d+):", re.M)
_ALGOS = {"1": "RSA", "22": "EdDSA/X25519"}


def parse_index(text: str) -> list[dict]:
    """Parse the machine-readable HKP index (op=index) into key dicts."""
    keys = []
    for fpr, algo, bits, created in _PUB_RE.findall(text):
        when = datetime.fromtimestamp(int(created), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        keys.append({"fingerprint": fpr, "algorithm": _ALGOS.get(algo, algo), "bits": bits or None, "created": when})
    return keys


class Proton(Module):
    name = "proton"
    title = "Proton key server"
    selector_types = frozenset({SelectorType.EMAIL})
    description = "Looks the address up on Proton's public PGP key server; a key means a Proton account, with key creation date."
    homepage = "https://proton.me/support/pgp-key-management"
    license = "API"
    tos = "Public HKP key server lookup, the same request a mail client makes before encrypting."
    can_notify = "no"
    base = "https://api.protonmail.ch/pks/lookup"

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        url = f"{self.base}?op=index&options=mr&search={quote(selector.value, safe='@')}"
        try:
            r = ctx.http.get(url)
        except httpx.HTTPError as exc:
            return [self.finding(selector, self.title, Status.ERROR, url=url, evidence=f"{type(exc).__name__}: {short(str(exc))}")]
        keys = parse_index(r.text) if r.status == 200 else []
        if keys:
            oldest = min(k["created"] for k in keys)
            return [self.finding(selector, self.title, Status.FOUND, url=url, http_status=r.status,
                                 evidence=f"{len(keys)} public key(s); oldest created {oldest} (approximate account age)",
                                 data={"keys": keys}, site_key="proton.me")]
        if r.status == 404 or "info:1:0" in r.text:
            return [self.finding(selector, self.title, Status.NOT_FOUND, url=url, http_status=r.status,
                                 evidence="no Proton key for this address", site_key="proton.me")]
        if r.status == 429:
            return [self.finding(selector, self.title, Status.BLOCKED, url=url, http_status=429, evidence="rate limited")]
        return [self.finding(selector, self.title, Status.UNKNOWN, url=url, http_status=r.status, evidence=f"HTTP {r.status}")]
