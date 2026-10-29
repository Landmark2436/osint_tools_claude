"""Small helpers shared by modules."""

from __future__ import annotations

import ipaddress
from functools import lru_cache
from importlib import resources
from urllib.parse import urlsplit

# Second-level labels under which registrable domains have three labels (example.co.uk).
_SECOND_LEVEL = {"co", "com", "org", "net", "ac", "gov", "edu", "ne", "or", "go"}


def short(text: str, limit: int = 80) -> str:
    """Collapse whitespace and cut text to limit characters."""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def site_key(url: str | None, fallback: str) -> str:
    """Registrable domain of a profile URL, used to match the same site across modules."""
    host = urlsplit(url).hostname if url else None
    if not host:
        return "".join(c for c in fallback.lower() if c.isalnum())
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    labels = host.lower().split(".")
    if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


@lru_cache(maxsize=None)
def data_list(name: str) -> frozenset[str]:
    """Load a vendored one-entry-per-line list from selector_recon/data (comments start with #)."""
    text = resources.files("selector_recon.data").joinpath(name).read_text(encoding="utf-8")
    return frozenset(s.strip().lower() for s in text.splitlines() if s.strip() and not s.lstrip().startswith("#"))


def registrable_domain(host: str) -> str:
    """example.co.uk for www.example.co.uk, example.com for a.b.example.com (approximation without the PSL)."""
    return site_key(f"http://{host}/", host)


def redact(text: str, *secrets: str | None) -> str:
    """Remove API keys from text that may end up in findings."""
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return text
