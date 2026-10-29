"""Core data types: selectors, findings and pivot hints."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SelectorType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    DOMAIN = "domain"
    IP = "ip"


class Status(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"
    ERROR = "error"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def utc_now() -> str:
    """Current UTC time as ISO 8601 with second precision, e.g. 2026-10-29T12:00:00Z."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Selector:
    value: str
    type: SelectorType

    def __str__(self) -> str:
        return f"{self.type.value}:{self.value}"


@dataclass(frozen=True)
class Pivot:
    """A new selector seen in a result. Listed in the report, never followed automatically."""

    type: SelectorType
    value: str
    reason: str

    def to_selector(self) -> Selector:
        return Selector(self.value, self.type)


@dataclass
class Finding:
    """One statement a source makes about a selector.

    `source` is the site or service the statement is about (e.g. "GitHub"),
    `module` the selector-recon module that produced it (e.g. "wmn").
    """

    selector: str
    selector_type: SelectorType
    module: str
    source: str
    status: Status
    url: str | None = None
    evidence: str = ""
    http_status: int | None = None
    screenshot: str | None = None
    confidence: Confidence = Confidence.MEDIUM
    category: str | None = None
    manual: bool = False
    data: dict[str, Any] = field(default_factory=dict)
    pivots: list[Pivot] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    site_key: str | None = None
    round: int = 0
    timestamp: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        # A blocked check always ends up in the manual-check list.
        if self.status is Status.BLOCKED:
            self.manual = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["selector_type"] = self.selector_type.value
        d["status"] = self.status.value
        d["confidence"] = self.confidence.value
        d["pivots"] = [{"type": p.type.value, "value": p.value, "reason": p.reason} for p in self.pivots]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Finding:
        d = dict(d)
        d["selector_type"] = SelectorType(d["selector_type"])
        d["status"] = Status(d["status"])
        d["confidence"] = Confidence(d.get("confidence", "medium"))
        d["pivots"] = [Pivot(SelectorType(p["type"]), p["value"], p["reason"]) for p in d.get("pivots", [])]
        return cls(**d)
