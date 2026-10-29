# selector-recon

Passive OSINT lookups for email addresses, phone numbers, usernames, domains and IPs.
Input: one or more selectors. Output: what public sources say about them, as evidence
you can paste into notes (source URL, UTC timestamp, status, short evidence).

> Work in progress (v0.1.0). Full documentation follows in a later stage.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install --no-deps -e .
.venv/bin/selector-recon --list-modules
.venv/bin/selector-recon alice_ctf --out runs/demo
```

Only run this on selectors you have a legitimate reason to investigate (CTF personas,
your own accounts). Do not use it on real private persons.
