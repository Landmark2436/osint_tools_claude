"""Output writers. Each run directory gets findings.json, findings.md and report.html."""

from __future__ import annotations

from pathlib import Path

from ..runner import RunResult
from .html import write_html
from .jsonout import result_to_dict, write_json
from .markdown import write_markdown

__all__ = ["result_to_dict", "write_all", "write_html", "write_json", "write_markdown"]


def write_all(result: RunResult, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return [
        write_json(result, out_dir / "findings.json"),
        write_markdown(result, out_dir / "findings.md"),
        write_html(result, out_dir / "report.html"),
    ]
