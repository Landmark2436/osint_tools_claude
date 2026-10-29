"""Print the README module table from the modules' own metadata, or update README.md in place.

Usage: python scripts/module_table.py [--write]
"""

from __future__ import annotations

import sys
from pathlib import Path

from selector_recon.modules import all_modules
from selector_recon.runner import parse_module_spec

README = Path(__file__).resolve().parent.parent / "README.md"
START, END = "<!-- module-table:start -->", "<!-- module-table:end -->"


def table() -> str:
    defaults = set(parse_module_spec(None))
    rows = [
        "| Module | Selectors | Default | Network | Key (env var) | Source | License | ToS / terms | Could notify the owner? |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, m in all_modules().items():
        types = ", ".join(sorted(t.value for t in m.selector_types))
        net = "browser" if m.needs_browser else ("yes" if m.needs_network else "no")
        key = f"`{m.needs_key}`" + (" (required)" if m.key_required else " (optional)") if m.needs_key else "-"
        source = f"[{m.title}]({m.homepage})" if m.homepage else m.title
        default = "yes" if name in defaults else "opt-in"
        rows.append(f"| `{name}` | {types} | {default} | {net} | {key} | {source} | {m.license} | {m.tos} | {m.can_notify} |")
    return "\n".join(rows)


def main() -> int:
    text = table()
    if "--write" not in sys.argv:
        print(text)
        return 0
    readme = README.read_text(encoding="utf-8")
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    README.write_text(f"{head}{START}\n{text}\n{END}{tail}", encoding="utf-8")
    print(f"updated {README}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
