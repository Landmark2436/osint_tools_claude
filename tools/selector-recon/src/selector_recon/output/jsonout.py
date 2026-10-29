"""findings.json: the full run, for machines."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..models import Status
from ..runner import RunResult

STATUS_ORDER = [s.value for s in Status]


def result_to_dict(result: RunResult) -> dict[str, Any]:
    counts = Counter(f.status.value for f in result.findings)
    return {
        "tool": "selector-recon",
        "version": result.tool_version,
        "started": result.started,
        "finished": result.finished,
        "interrupted": result.interrupted,
        "selectors": [{"value": s.value, "type": s.type.value} for s in result.selectors],
        "summary": {s: counts.get(s, 0) for s in STATUS_ORDER},
        "config": result.config,
        "module_runs": [asdict(r) for r in result.module_runs],
        "findings": [f.to_dict() for f in result.findings],
        "manual_checks": [
            {"selector": f.selector, "module": f.module, "source": f.source, "url": f.url, "reason": f.evidence}
            for f in result.manual_checks
        ],
        "pivots": [
            {"type": p.type.value, "value": p.value, "reason": p.reason, "seen_in": seen}
            for p, seen in result.pivots
        ],
    }


def write_json(result: RunResult, path: Path) -> Path:
    path.write_text(json.dumps(result_to_dict(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
