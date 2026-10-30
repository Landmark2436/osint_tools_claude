# IP & Domain Lookup

Looks up an IP address or a domain in free public sources without API keys. For an IP it shows reverse DNS, the network owner and the domains seen on that IP. For a domain it shows the current DNS records, the registration and the IP history.

**Status:** experimental · **Version:** 0.1.0 · **Open:** [`index.html`](index.html)

## Quick start

**Online:** <https://landmark2436.github.io/osint_tools_claude/tools/ip-domain-lookup/> (once GitHub Pages is enabled for this repository).

**Offline copy:** open `tools/ip-domain-lookup/index.html` in a browser (double-click). The lookups themselves need an internet connection.

Enter `93.184.215.14` or `example.com` and press **Look up**. Click any IP or domain in the results to look it up next.

## Modes / features

| Input | Result |
|---|---|
| IPv4 or IPv6 address | Reverse DNS (PTR), network name, owner, range, country, abuse contact, AS number, open ports, domains seen on the IP with first and last seen |
| Domain or hostname | Current A, AAAA, CNAME, MX, NS and TXT records, registrar and registration dates, DNS history (A, AAAA, CNAME, NS, MX) with first and last seen, subdomains seen |

- Input is cleaned up: URLs (`https://www.example.com/path`), ports, `user@` prefixes, defanged indicators (`example[.]com`, `hxxps://`) and internationalized domains (`bücher.de`).
- Results appear source by source; a status line shows what each source returned or why it failed.
- Domain lists and the history can be copied or exported as CSV.
- Private and reserved addresses (e.g. `192.168.x.x`, `10.x.x.x`, `fe80::`) are not sent anywhere.
- A note appears when the IP belongs to a CDN (Cloudflare, Akamai, Fastly …) or when it hosts very many domains (shared hosting).
- **Check manually** links open the same query on ViewDNS, SecurityTrails, VirusTotal, Shodan, urlscan.io, crt.sh, Robtex and others in a new tab.
- The query is kept in the page address (`…/index.html#example.com`), so a lookup can be bookmarked. Opening such a link fills in the field but does not send anything until you press Look up.

## Sources

| Source | Used for | Mode | Notes |
|---|---|---|---|
| DNS over HTTPS, [dns.google](https://developers.google.com/speed/public-dns/docs/doh/json) (fallback [Cloudflare](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/)) | PTR and current DNS records | IP, domain | |
| [RDAP](https://about.rdap.org/) via rdap.org | Network owner, domain registration | IP, domain | Some registries (e.g. DENIC for `.de`) publish little or nothing |
| [RIPEstat](https://stat.ripe.net/) | AS number and announced prefix | IP | Worldwide, not only the RIPE region |
| [Shodan InternetDB](https://internetdb.shodan.io/) | Hostnames, open ports, tags | IP | Free for non-commercial use |
| [HackerTarget](https://hackertarget.com/reverse-ip-lookup/) | Reverse IP (domains on the IP) | IP | Few free lookups per day per IP address |
| mnemonic Passive DNS (api.mnemonic.no) | Passive DNS with first and last seen | IP, domain | Rate-limited without a key |
| [AlienVault OTX](https://otx.alienvault.com/api) | Passive DNS with first and last seen, subdomains | IP, domain | Rate-limited without a key |

Each source can be switched off under the search field; the choice is saved in the browser (localStorage).

## How it works

DNS cannot answer “which domains point to this IP?”, because there is no reverse index; the PTR record only holds the one name the owner of the IP range chose. The domain list and the IP history therefore come from **passive DNS** databases, which record DNS answers observed over time, and from scan data. The tool queries all enabled sources in parallel, merges the results per domain or per record, keeps the earliest *first seen* and latest *last seen*, and shows which sources reported each entry.

## Limitations

- Results are never complete. Each database only knows what it has observed; small or new sites are often missing, and HackerTarget and InternetDB give no dates.
- Shared hosting and CDNs: one IP can carry thousands of unrelated sites, and behind a CDN the real server IP is hidden.
- First and last seen are the dates a source *observed* a record, not the exact dates it was set or removed.
- The tool calls the sources directly from the browser. A source that does not allow this (CORS), is down or has hit its rate limit shows a warning in the status line; the others keep working. Use **Check manually** in that case.
- The sources' free tiers, endpoints and limits can change without notice.

## Self-test

Click **Self-test** at the bottom of the page. 14 checks run offline with sample data: input clean-up (IPv4, IPv6, URLs, defanged and internationalized input, invalid input), PTR names for IPv4 and IPv6, reserved ranges, the parsers for every source, merging of the IP and domain results, CDN detection, CSV and HTML escaping. They do not contact the sources.

## Browser compatibility

Current Chrome, Edge, Firefox and Safari, desktop and mobile; light and dark mode follow the system. Plain ES2020 without modules, so it also works via `file://`.

## Privacy

**This tool sends your query to third parties.** When you press Look up, or click an IP or domain in the results, the IP or domain is sent to every enabled source listed above. Those services may log it together with your IP address. Nothing is sent while typing, and private or reserved addresses are never sent. Links under *Check manually* send the query only when clicked. The tool stores only your source selection in the browser. No tracking, no analytics, no API keys.

## Third-party libraries and attributions

No libraries. Data comes from the services listed under [Sources](#sources), subject to their terms of use. Shodan InternetDB is free for non-commercial use.

## Changelog

### v0.1.0 – 2026-10-30

- Initial release: reverse DNS, network owner and AS, domains on an IP, current DNS records, domain registration, DNS history and subdomains from seven free sources without API keys.
