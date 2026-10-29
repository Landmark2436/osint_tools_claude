"""findings.md: paste-ready evidence for challenge notes."""

from __future__ import annotations

from pathlib import Path

from ..models import Finding, Status
from ..runner import RunResult

# Order inside each selector section: hits first, noise last.
_RANK = {Status.FOUND: 0, Status.BLOCKED: 1, Status.UNKNOWN: 2, Status.ERROR: 3, Status.NOT_FOUND: 4}


def _cell(text: object) -> str:
    return str(text or "").replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").strip()


def _link(url: str | None) -> str:
    if not url:
        return ""
    return f"<{url}>" if " " not in url else _cell(url)


def _row(f: Finding) -> str:
    evidence = f.evidence
    if f.flags:
        evidence += " (" + "; ".join(f.flags) + ")"
    if f.screenshot:
        evidence += f" [screenshot: {f.screenshot}]"
    return (
        f"| {f.status.value} | {_cell(f.source)} | {_link(f.url)} | {_cell(evidence)} "
        f"| {f.confidence.value} | {f.module} | {f.timestamp} |"
    )


def render_markdown(result: RunResult, include_not_found: bool = False) -> str:
    lines = [
        "# selector-recon findings",
        "",
        f"- Run: {result.started} to {result.finished} (UTC), selector-recon {result.tool_version}"
        + (" — **interrupted, partial results**" if result.interrupted else ""),
        f"- Selectors: {', '.join(f'`{s.value}` ({s.type.value})' for s in result.selectors)}",
        f"- Modules: {', '.join(result.config.get('modules_resolved', []))}",
        "",
    ]
    for sel in result.selectors:
        rows = [f for f in result.findings if f.selector == sel.value and f.selector_type is sel.type]
        hidden = [f for f in rows if f.status is Status.NOT_FOUND]
        shown = rows if include_not_found else [f for f in rows if f.status is not Status.NOT_FOUND]
        shown.sort(key=lambda f: (_RANK[f.status], f.source.lower()))
        lines += [f"## `{sel.value}` ({sel.type.value})", ""]
        if shown:
            lines += [
                "| Status | Source | URL | Evidence | Confidence | Module | Checked (UTC) |",
                "|---|---|---|---|---|---|---|",
                *(_row(f) for f in shown),
            ]
        else:
            lines.append("No positive, blocked or inconclusive results.")
        if hidden and not include_not_found:
            lines += ["", f"{len(hidden)} source(s) reported not found; see findings.json or report.html."]
        lines.append("")
    if result.manual_checks:
        lines += ["## Manual checks", ""]
        for f in result.manual_checks:
            lines.append(f"- [ ] `{f.selector}` — {_cell(f.source)}: <{f.url}> ({_cell(f.evidence)})")
        lines.append("")
    if result.pivots:
        lines += ["## Pivot hints (not followed)", ""]
        for p, seen in result.pivots:
            lines.append(f"- {p.type.value} `{p.value}` — {_cell(p.reason)} (from {', '.join(seen)})")
        lines.append("")
    skipped = [r for r in result.module_runs if r.state != "ran"]
    if skipped:
        lines += ["## Skipped or failed modules", ""]
        for r in skipped:
            lines.append(f"- `{r.selector}` {r.module}: {r.state} ({_cell(r.reason)})")
        lines.append("")
    return "\n".join(lines)


def write_markdown(result: RunResult, path: Path) -> Path:
    path.write_text(render_markdown(result), encoding="utf-8")
    return path
