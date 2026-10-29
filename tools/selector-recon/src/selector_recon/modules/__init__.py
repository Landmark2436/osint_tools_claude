"""Module registry. Every Module subclass with a `name` in this package is picked up automatically."""

from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache

from .base import Module, RunContext

__all__ = ["Module", "RunContext", "all_modules", "get_module"]


@lru_cache(maxsize=1)
def all_modules() -> dict[str, Module]:
    found: dict[str, Module] = {}
    for info in pkgutil.walk_packages(__path__, prefix=f"{__name__}."):
        mod = importlib.import_module(info.name)
        for obj in vars(mod).values():
            if isinstance(obj, type) and issubclass(obj, Module) and "name" in vars(obj):
                if obj.name in found and type(found[obj.name]) is not obj:
                    raise RuntimeError(f"duplicate module name {obj.name!r}")
                found[obj.name] = obj()
    return dict(sorted(found.items()))


def get_module(name: str) -> Module:
    try:
        return all_modules()[name]
    except KeyError:
        raise KeyError(f"unknown module {name!r}; see --list-modules") from None
