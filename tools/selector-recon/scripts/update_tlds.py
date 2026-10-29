"""Regenerate src/selector_recon/data/tlds.txt from the Public Suffix List (ICANN section).

Usage: python scripts/update_tlds.py [path-to-public_suffix_list.dat]
Without a path the list is downloaded from the publicsuffix/list GitHub mirror.
"""

from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path

PSL_URL = "https://raw.githubusercontent.com/publicsuffix/list/main/public_suffix_list.dat"
OUT = Path(__file__).resolve().parent.parent / "src" / "selector_recon" / "data" / "tlds.txt"


def tlds_from_psl(text: str) -> set[str]:
    tlds: set[str] = set()
    icann = False
    for line in text.splitlines():
        s = line.strip()
        if "BEGIN ICANN DOMAINS" in s:
            icann = True
        elif "END ICANN DOMAINS" in s:
            icann = False
        if not icann or not s or s.startswith("//"):
            continue
        tld = s.lstrip("!*.").split(".")[-1].lower()
        tlds.add(tld if tld.isascii() else tld.encode("idna").decode("ascii"))
    return tlds


def main() -> int:
    if len(sys.argv) > 1:
        text, source = Path(sys.argv[1]).read_text(encoding="utf-8"), sys.argv[1]
    else:
        with urllib.request.urlopen(PSL_URL, timeout=30) as resp:
            text = resp.read().decode("utf-8")
        head = subprocess.run(
            ["git", "ls-remote", "https://github.com/publicsuffix/list", "refs/heads/main"],
            capture_output=True, text=True, check=False,
        ).stdout.split()
        source = f"commit {head[0]}" if head else PSL_URL
    tlds = tlds_from_psl(text)
    lines = [
        "# Top-level domains, derived from the ICANN section of the Public Suffix List",
        f"# https://publicsuffix.org/ (MPL-2.0), {source}",
        "# Regenerate with scripts/update_tlds.py",
        *sorted(tlds),
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"wrote {len(tlds)} TLDs to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
