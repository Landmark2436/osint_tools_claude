"""Command-line interface: selector-recon <selector> [...]"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .detect import make_selector
from .models import SelectorType, Status
from .modules import all_modules
from .output import write_all
from .runner import RunConfig, Runner, parse_module_spec

EPILOG = """examples:
  selector-recon johndoe42
  selector-recon user@example.com +12015550123 --out runs/case1
  selector-recon john.doe --type username --modules wmn,maigret
  selector-recon user@example.com --modules +holehe --pivot 1
  selector-recon --offline user@example.com

Only use this on selectors you are allowed to investigate (CTF personas, your own accounts).
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="selector-recon",
        description="Passive OSINT lookups for email addresses, phone numbers, usernames, domains and IPs.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("selectors", nargs="*", help="one or more selectors; type is auto-detected")
    p.add_argument("-f", "--file", type=Path, help="read selectors from a file, one per line (# comments allowed)")
    p.add_argument("-t", "--type", choices=[t.value for t in SelectorType], help="force the selector type for all inputs")
    p.add_argument("-m", "--modules", help="'a,b' runs exactly these; '+a,-b' changes the defaults; 'all' runs everything")
    p.add_argument("--list-modules", action="store_true", help="list modules and exit")
    p.add_argument("-o", "--out", type=Path, help="output directory (default: runs/<UTC timestamp>)")
    p.add_argument("--offline", action="store_true", help="only run modules that need no network")
    p.add_argument("--timeout", type=float, default=10.0, help="per-request timeout in seconds (default 10)")
    p.add_argument("--rate", type=float, default=1.0, help="max requests per second per host (default 1)")
    p.add_argument("--workers", type=int, default=16, help="parallel requests across hosts (default 16)")
    p.add_argument("--pivot", type=int, choices=[0, 1], default=0, help="follow pivot hints one level deep (default 0)")
    p.add_argument("--no-nsfw", action="store_true", help="skip sites tagged NSFW (included by default)")
    p.add_argument("--obey-robots", action="store_true", help="also apply robots.txt to plain HTTP modules")
    p.add_argument("--browser-ua", action="store_true",
                   help="send a fixed desktop-browser User-Agent instead of the honest selector-recon one")
    p.add_argument("--dns-server", action="append", metavar="IP", help="DNS server to use instead of the system resolver (repeatable)")
    p.add_argument("--env-file", type=Path, default=Path(".env"), help="file with API keys as KEY=value (default ./.env)")
    p.add_argument("--region", default=None, help="default region for phone numbers without +country code, e.g. DE")
    p.add_argument("--wmn-data", type=Path, help="use this wmn-data.json instead of the pinned upstream copy")
    p.add_argument("--maigret-top", type=int, default=500, help="number of top-ranked Maigret sites (default 500)")
    p.add_argument("--cache-dir", type=Path, help="cache for downloaded data files (default ~/.cache/selector-recon)")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    p.add_argument("-q", "--quiet", action="store_true", help="no progress output")
    p.add_argument("--version", action="version", version=f"selector-recon {__version__}")
    return p


def list_modules() -> str:
    defaults = set(parse_module_spec(None))
    lines = [f"{'module':<14} {'default':<8} {'types':<24} {'net':<4} {'browser':<8} {'key':<17} description"]
    for name, m in all_modules().items():
        types = ",".join(sorted(t.value for t in m.selector_types))
        lines.append(
            f"{name:<14} {'yes' if name in defaults else 'opt-in':<8} {types:<24} {'yes' if m.needs_network else 'no':<4} "
            f"{'yes' if m.needs_browser else 'no':<8} {m.needs_key or '-':<17} {m.description}"
        )
        reason = m.unavailable_reason()
        if reason:
            lines.append(f"{'':<14} unavailable: {reason}")
    return "\n".join(lines)


def load_env_file(path: Path) -> list[str]:
    """Load KEY=value lines into os.environ without overriding variables that are already set.

    Returns the names that were loaded (never the values)."""
    if not path.is_file():
        return []
    loaded = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip("'\"")
        if key and value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def read_selectors(args: argparse.Namespace) -> list[str]:
    values = list(args.selectors)
    if args.file:
        for line in args.file.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                values.append(line)
    return values


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )
    # httpx logs full request URLs at debug level; some APIs (Shodan) take the key as a URL parameter.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    loaded = load_env_file(args.env_file)
    if args.list_modules:
        print(list_modules())
        return 0
    raw = read_selectors(args)
    if not raw:
        parser.error("no selectors given")
    forced = SelectorType(args.type) if args.type else None
    try:
        selectors = [make_selector(v, forced) for v in raw]
        parse_module_spec(args.modules)  # fail early on unknown module names
    except (KeyError, ValueError) as exc:
        parser.error(str(exc.args[0] if exc.args else exc))

    out_dir = args.out or Path("runs") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    config = RunConfig(
        out_dir=out_dir,
        modules=args.modules,
        offline=args.offline,
        timeout=args.timeout,
        rate=args.rate,
        pivot=args.pivot,
        include_nsfw=not args.no_nsfw,
        obey_robots=args.obey_robots,
        browser_ua=args.browser_ua,
        dns_servers=args.dns_server,
        cache_dir=args.cache_dir,
        options={
            "workers": args.workers,
            "region": args.region,
            "wmn_data": str(args.wmn_data) if args.wmn_data else None,
            "maigret_top": args.maigret_top,
        },
    )
    progress = (lambda msg: None) if args.quiet else (lambda msg: print(msg, file=sys.stderr, flush=True))
    if loaded:
        progress(f"loaded from {args.env_file}: {', '.join(loaded)}")
    for s in selectors:
        progress(f"selector {s.value!r}: {s.type.value}")
    runner = Runner(config, progress=progress)
    try:
        result = runner.run(selectors)
    finally:
        runner.http.close()
    paths = write_all(result, out_dir)
    counts = {s.value: sum(f.status is s for f in result.findings) for s in Status}
    progress("summary: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    progress(f"manual checks: {len(result.manual_checks)}, pivot hints: {len(result.pivots)}")
    for path in paths:
        print(path)
    return 130 if result.interrupted else 0
