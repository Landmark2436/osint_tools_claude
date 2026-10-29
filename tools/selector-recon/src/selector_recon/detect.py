"""Selector type auto-detection.

Detection is a best guess. Ambiguous inputs (a dotted username that ends in a
real TLD, a digit-only username) can be forced with --type.
"""

from __future__ import annotations

import ipaddress
import re
from functools import lru_cache
from importlib import resources

from .models import Selector, SelectorType

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_CHARS_RE = re.compile(r"^\+?[0-9 ()./\-]+$")
_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


@lru_cache(maxsize=1)
def known_tlds() -> frozenset[str]:
    text = resources.files("selector_recon.data").joinpath("tlds.txt").read_text(encoding="ascii")
    return frozenset(line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#"))


def looks_like_domain(value: str) -> bool:
    value = value.lower().rstrip(".")
    try:
        value = value.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    labels = value.split(".")
    if len(labels) < 2 or not all(_LABEL_RE.match(label) for label in labels):
        return False
    return labels[-1] in known_tlds()


def normalize(value: str, type_: SelectorType) -> str:
    value = value.strip()
    if type_ is SelectorType.USERNAME:
        return value.lstrip("@")
    if type_ in (SelectorType.EMAIL, SelectorType.DOMAIN):
        return value.lower().rstrip(".")
    if type_ is SelectorType.IP:
        return str(ipaddress.ip_address(value))
    return value


def detect_type(value: str) -> SelectorType:
    value = value.strip()
    try:
        ipaddress.ip_address(value)
        return SelectorType.IP
    except ValueError:
        pass
    if _EMAIL_RE.match(value):
        return SelectorType.EMAIL
    if _PHONE_CHARS_RE.match(value) and sum(c.isdigit() for c in value) >= 7:
        return SelectorType.PHONE
    if not value.startswith("@") and looks_like_domain(value):
        return SelectorType.DOMAIN
    return SelectorType.USERNAME


def make_selector(value: str, type_: SelectorType | None = None) -> Selector:
    type_ = type_ or detect_type(value)
    return Selector(normalize(value, type_), type_)
