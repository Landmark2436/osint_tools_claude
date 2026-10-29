"""Run modules against selectors, isolate failures, cross-check sources, collect pivots."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import __version__
from .http import HttpClient
from .models import Confidence, Finding, Pivot, Selector, Status, utc_now
from .modules import Module, RunContext, all_modules, get_module

log = logging.getLogger("selector_recon")

@dataclass
class RunConfig:
    out_dir: Path
    modules: str | None = None
    offline: bool = False
    timeout: float = 10.0
    rate: float = 1.0
    pivot: int = 0
    include_nsfw: bool = True
    obey_robots: bool = False
    cache_dir: Path | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleRun:
    selector: str
    module: str
    state: str  # ran | skipped | failed
    reason: str = ""
    findings: int = 0
    seconds: float = 0.0
    round: int = 0


@dataclass
class RunResult:
    started: str
    finished: str
    selectors: list[Selector]
    findings: list[Finding]
    module_runs: list[ModuleRun]
    config: dict[str, Any]
    interrupted: bool = False
    tool_version: str = __version__

    @property
    def manual_checks(self) -> list[Finding]:
        return [f for f in self.findings if f.manual and f.url]

    @property
    def pivots(self) -> list[tuple[Pivot, list[str]]]:
        """Unique pivot hints with the modules that produced them."""
        seen: dict[tuple[str, str], tuple[Pivot, list[str]]] = {}
        known = {(s.type.value, s.value.lower()) for s in self.selectors}
        for f in self.findings:
            for p in f.pivots:
                key = (p.type.value, p.value.lower())
                if key in known:
                    continue
                entry = seen.setdefault(key, (p, []))
                label = f"{f.module}/{f.source}"
                if label not in entry[1]:
                    entry[1].append(label)
        return list(seen.values())


def parse_module_spec(spec: str | None) -> list[str]:
    """`None` = defaults, `a,b` = exactly these, `+a,-b` = defaults plus a without b, `all` = everything."""
    mods = all_modules()
    defaults = [n for n, m in mods.items() if m.default_enabled]
    if not spec:
        return defaults
    tokens = [t.strip() for t in spec.split(",") if t.strip()]
    if all(t[0] in "+-" for t in tokens):
        chosen = list(defaults)
        for t in tokens:
            name = t[1:]
            if name == "all":
                chosen = list(mods) if t[0] == "+" else []
                continue
            get_module(name)
            if t[0] == "+" and name not in chosen:
                chosen.append(name)
            elif t[0] == "-" and name in chosen:
                chosen.remove(name)
        return chosen
    if tokens == ["all"]:
        return list(mods)
    for t in tokens:
        if t[0] in "+-":
            raise ValueError("mix of plain and +/- module names; use either 'a,b' or '+a,-b'")
        get_module(t)
    return tokens


def cross_check(findings: list[Finding]) -> None:
    """Flag sites where account-existence modules agree or disagree, in place."""
    groups: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for f in findings:
        if f.site_key and f.status in (Status.FOUND, Status.NOT_FOUND):
            groups[(f.selector, f.site_key)].append(f)
    for group in groups.values():
        modules = {f.module for f in group}
        if len(modules) < 2:
            continue
        found = {f.module for f in group if f.status is Status.FOUND}
        missing = {f.module for f in group if f.status is Status.NOT_FOUND}
        if found and missing:
            flag = f"sources disagree: found by {', '.join(sorted(found))}; not found by {', '.join(sorted(missing))}"
            for f in group:
                f.flags.append(flag)
                f.confidence = Confidence.LOW
        else:
            for f in group:
                f.flags.append(f"confirmed by {len(modules)} modules")
                f.confidence = Confidence.HIGH


class Runner:
    def __init__(
        self,
        config: RunConfig,
        http: HttpClient | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.http = http or HttpClient(timeout=config.timeout, rate=config.rate, obey_robots=config.obey_robots)
        self.progress = progress or (lambda msg: log.info(msg))
        self.module_names = parse_module_spec(config.modules)
        self.ctx = RunContext(
            http=self.http,
            out_dir=config.out_dir,
            timeout=config.timeout,
            include_nsfw=config.include_nsfw,
            cache_dir=config.cache_dir,
            options=config.options,
        )

    def _skip_reason(self, module: Module) -> str | None:
        if self.config.offline and module.needs_network:
            return "offline mode"
        return module.unavailable_reason(self.ctx)

    def run(self, selectors: Iterable[Selector]) -> RunResult:
        selectors = list(dict.fromkeys(selectors))
        started = utc_now()
        findings: list[Finding] = []
        runs: list[ModuleRun] = []
        interrupted = False
        done: set[Selector] = set()
        try:
            todo = selectors
            for round_ in range(self.config.pivot + 1):
                for sel in todo:
                    done.add(sel)
                    findings.extend(self._run_selector(sel, round_, runs))
                if round_ == self.config.pivot:
                    break
                todo = []
                for f in findings:
                    for p in f.pivots:
                        s = p.to_selector()
                        if s not in done and s not in todo:
                            todo.append(s)
                if not todo:
                    break
                self.progress(f"pivot round {round_ + 1}: {len(todo)} new selector(s)")
                selectors.extend(todo)
        except KeyboardInterrupt:
            interrupted = True
            self.progress("interrupted, writing partial results")
        cross_check(findings)
        return RunResult(
            started=started,
            finished=utc_now(),
            selectors=selectors,
            findings=findings,
            module_runs=runs,
            config=self._config_summary(),
            interrupted=interrupted,
        )

    def _run_selector(self, sel: Selector, round_: int, runs: list[ModuleRun]) -> list[Finding]:
        out: list[Finding] = []
        modules = [get_module(n) for n in self.module_names]
        # Browser modules run last and one at a time; the rest run in the order given.
        modules.sort(key=lambda m: m.needs_browser)
        for module in modules:
            if sel.type not in module.selector_types:
                continue
            reason = self._skip_reason(module)
            if reason:
                runs.append(ModuleRun(sel.value, module.name, "skipped", reason, round=round_))
                self.progress(f"[{sel}] {module.name}: skipped ({reason})")
                continue
            self.progress(f"[{sel}] {module.name}: running")
            t0 = time.monotonic()
            try:
                result = module.run(sel, self.ctx)
                state, why = "ran", ""
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # a failing module never fails the run
                log.debug("module %s failed", module.name, exc_info=True)
                result = [module.finding(sel, module.title, Status.ERROR, evidence=f"module failed: {type(exc).__name__}: {exc}")]
                state, why = "failed", f"{type(exc).__name__}: {exc}"
            for f in result:
                f.round = round_
            runs.append(ModuleRun(sel.value, module.name, state, why, len(result), round(time.monotonic() - t0, 2), round_))
            counts = defaultdict(int)
            for f in result:
                counts[f.status.value] += 1
            self.progress(f"[{sel}] {module.name}: {state}, " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
            out.extend(result)
        return out

    def _config_summary(self) -> dict[str, Any]:
        d = asdict(self.config)
        d["out_dir"] = str(self.config.out_dir)
        d["cache_dir"] = str(self.config.cache_dir) if self.config.cache_dir else None
        d["modules_resolved"] = self.module_names
        return d
