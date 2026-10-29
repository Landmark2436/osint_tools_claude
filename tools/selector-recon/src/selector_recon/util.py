"""Small helpers shared by modules."""

from __future__ import annotations

import ipaddress
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
