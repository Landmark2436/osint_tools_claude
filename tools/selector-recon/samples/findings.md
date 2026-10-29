# selector-recon findings

- Run: 2026-10-29T07:45:09Z to 2026-10-29T07:45:09Z (UTC), selector-recon 0.1.0
- Selectors: `user@example.com` (email), `+4915123456789` (phone), `mrrobot` (username), `example.com` (domain), `192.0.2.1` (ip)
- Modules: crtsh, dns, email_info, gravatar, hibp, ip_info, maigret, phone_info, phone_links, proton, rdap, sherlock, shodan, wayback, wmn

## `user@example.com` (email)

| Status | Source | URL | Evidence | Confidence | Module | Checked (UTC) |
|---|---|---|---|---|---|---|
| found | Email syntax |  | valid syntax (reserved example domain (RFC 2606): not a real mailbox) | high | email_info | 2026-10-29T07:45:09Z |

## `+4915123456789` (phone)

| Status | Source | URL | Evidence | Confidence | Module | Checked (UTC) |
|---|---|---|---|---|---|---|
| found | phonenumbers |  | valid; mobile; +4915123456789; Germany; carrier T-Mobile (original allocation; ported numbers differ); tz Europe/Berlin | high | phone_info | 2026-10-29T07:45:09Z |

6 manual lookup link(s) under Manual checks.

## `mrrobot` (username)

No results: every module for this selector was skipped (see Skipped or failed modules).

## `example.com` (domain)

No results: every module for this selector was skipped (see Skipped or failed modules).

## `192.0.2.1` (ip)

| Status | Source | URL | Evidence | Confidence | Module | Checked (UTC) |
|---|---|---|---|---|---|---|
| found | IP address |  | IPv4, private; PTR name 1.2.0.192.in-addr.arpa (documentation range (RFC 5737/3849): example address) | high | ip_info | 2026-10-29T07:45:09Z |

## Manual checks

- [ ] `+4915123456789` — Google search: <https://www.google.com/search?q=%22%2B4915123456789%22%20OR%20%22%2B49%201512%203456789%22%20OR%20%2201512%203456789%22> (manual lookup link, not opened by selector-recon; exact-match search for common formats)
- [ ] `+4915123456789` — DuckDuckGo search: <https://duckduckgo.com/?q=%22%2B4915123456789%22%20OR%20%22%2B49%201512%203456789%22%20OR%20%2201512%203456789%22> (manual lookup link, not opened by selector-recon; exact-match search for common formats)
- [ ] `+4915123456789` — Bing search: <https://www.bing.com/search?q=%22%2B4915123456789%22%20OR%20%22%2B49%201512%203456789%22%20OR%20%2201512%203456789%22> (manual lookup link, not opened by selector-recon; exact-match search for common formats)
- [ ] `+4915123456789` — WhatsApp: <https://wa.me/4915123456789> (manual lookup link, not opened by selector-recon; opens a chat page; sending nothing notifies nobody)
- [ ] `+4915123456789` — Telegram: <https://t.me/+4915123456789> (manual lookup link, not opened by selector-recon; resolves only if the owner allows lookup by number)
- [ ] `+4915123456789` — Truecaller: <https://www.truecaller.com/search/de/15123456789> (manual lookup link, not opened by selector-recon; needs a Truecaller login; their ToS apply)

## Pivot hints (not followed)

- username `user` — local part of the email address (from email_info/Email syntax)

## Skipped or failed modules

- `user@example.com` dns: skipped (offline mode)
- `user@example.com` gravatar: skipped (offline mode)
- `user@example.com` hibp: skipped (offline mode)
- `user@example.com` proton: skipped (offline mode)
- `mrrobot` maigret: skipped (offline mode)
- `mrrobot` sherlock: skipped (offline mode)
- `mrrobot` wmn: skipped (offline mode)
- `example.com` crtsh: skipped (offline mode)
- `example.com` dns: skipped (offline mode)
- `example.com` rdap: skipped (offline mode)
- `example.com` wayback: skipped (offline mode)
- `192.0.2.1` dns: skipped (offline mode)
- `192.0.2.1` rdap: skipped (offline mode)
- `192.0.2.1` shodan: skipped (offline mode)
