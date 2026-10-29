# Sample run (offline)

Generated with only the modules that need no network, on selectors that belong to nobody:

```bash
selector-recon --offline --out samples \
  user@example.com +4915123456789 mrrobot example.com 192.0.2.1
```

- `user@example.com`: RFC 2606 reserved domain
- `+4915123456789`: the example mobile number `phonenumbers` ships for Germany
- `mrrobot`: a fictional username
- `example.com`, `192.0.2.1`: reserved example domain and documentation IP range (RFC 5737)

Files: [`findings.md`](findings.md) (paste-ready notes), [`findings.json`](findings.json)
(machine-readable), [`report.html`](report.html) (open in a browser; filters, manual checks, pivots).
Network modules show as "skipped (offline mode)".
