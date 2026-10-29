"""Module interface. One source = one subclass of Module in its own file."""

from __future__ import annotations

import importlib.util
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from ..models import Confidence, Finding, Selector, SelectorType, Status

if TYPE_CHECKING:
    from ..http import HttpClient

log = logging.getLogger("selector_recon")


@dataclass
class RunContext:
    """Everything a module may use during a run. Modules get no other global state."""

    http: HttpClient
    out_dir: Path
    timeout: float = 10.0
    include_nsfw: bool = True
    cache_dir: Path | None = None
    options: dict[str, Any] = field(default_factory=dict)
    browser: Any = None  # set by the runner when a browser module runs

    def env(self, name: str) -> str | None:
        value = os.environ.get(name, "").strip()
        return value or None


class Module:
    name: ClassVar[str]
    title: ClassVar[str]
    selector_types: ClassVar[frozenset[SelectorType]]
    needs_network: ClassVar[bool] = True
    needs_browser: ClassVar[bool] = False
    needs_key: ClassVar[str | None] = None  # env var name; without it the module runs in reduced mode or is skipped
    key_required: ClassVar[bool] = False  # True: skip entirely without the key
    default_enabled: ClassVar[bool] = True
    requires: ClassVar[tuple[str, ...]] = ()  # importable packages from optional extras
    install_hint: ClassVar[str] = ""
    # Documentation, rendered into the README module table and `--list-modules`.
    description: ClassVar[str] = ""
    homepage: ClassVar[str] = ""
    license: ClassVar[str] = ""
    tos: ClassVar[str] = ""
    can_notify: ClassVar[str] = "no"

    def unavailable_reason(self, ctx: RunContext | None = None) -> str | None:
        """Why this module cannot run right now, or None if it can."""
        missing = [pkg for pkg in self.requires if importlib.util.find_spec(pkg) is None]
        if missing:
            return f"missing package(s) {', '.join(missing)}" + (f"; {self.install_hint}" if self.install_hint else "")
        if self.key_required and self.needs_key and not os.environ.get(self.needs_key, "").strip():
            return f"needs API key in ${self.needs_key}"
        return None

    def run(self, selector: Selector, ctx: RunContext) -> list[Finding]:
        raise NotImplementedError

    # Helpers so modules build findings consistently.
    def finding(self, selector: Selector, source: str, status: Status, **kwargs: Any) -> Finding:
        kwargs.setdefault("confidence", Confidence.LOW if status in (Status.UNKNOWN, Status.ERROR) else Confidence.MEDIUM)
        return Finding(
            selector=selector.value,
            selector_type=selector.type,
            module=self.name,
            source=source,
            status=status,
            **kwargs,
        )
