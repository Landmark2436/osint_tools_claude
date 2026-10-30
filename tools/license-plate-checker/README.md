# License Plate Checker

Checks German number plates (*Kfz-Kennzeichen*): validates the format, finds the registration authority (*Zulassungsbehörde*) that issues the code, and leads you to that authority's official *Wunschkennzeichen* portal to find out whether the plate is still available. Results can be logged with a date and exported. For checking many plates, there is a batch mode.

**Status:** beta · **Version:** 0.1.0 · **Open:** [`index.html`](index.html)

## Is there a central database?

No. Germany has no public, central register of issued plates. Each of the roughly 400 registration authorities (districts and independent cities) keeps its own register and runs its own reservation portal, usually through one of several municipal IT providers. The vehicle register of the KBA (*Zentrales Fahrzeugregister*) is not public; information about owners (*Halterauskunft*) is only given when there is a legitimate interest (§ 39 StVG).

A page on GitHub Pages also can't query the portals automatically: they don't allow requests from other websites (CORS), work with sessions and often use captchas. That's why the tool does everything that can be done offline (format, rules, authority) and leaves the final check to you, on the official portal.

## Quick start

**Online (recommended):** <https://landmark2436.github.io/osint_tools_claude/tools/license-plate-checker/> (once GitHub Pages is enabled for this repository).

**Offline copy:** open `tools/license-plate-checker/index.html` in a current browser (double-click). The tool needs no libraries and no internet connection; only the search and portal links open external pages.

1. Enter a plate, e.g. `M-AB 1234`, `mab1234` or `LOS-K 12H`.
2. Read the format check. Errors mean the plate can't be issued; warnings mean many authorities refuse it.
3. In **Issuing authority & availability**, open the official portal: use a saved link, or find it with the DuckDuckGo or Google button. Copy the code, letters and number into the portal form.
4. Record what the portal says (**Available**, **Not available**, **Reserved by me**, **Unclear**). The entry is added to the **Check log**.

## Features

| Feature | Input | Result |
|---|---|---|
| Format check | one plate in any notation | Readings of the input, rule-by-rule check (error / warning / info) |
| Issuing authority | (from the plate) | District or city and state; both authorities if a city and a district share the code |
| Portal links | (from the authority) | Search links for the official portal; your own saved portal link per authority |
| Check log | portal result + note | Dated log, CSV export, JSON backup and restore |
| Batch check | list of plates | Table with format result, authority and last logged result; CSV export |
| Code lookup | code, district or state | Searchable table of all 704 codes |

## Input

- Upper or lower case; separators `-`, space, `:`, `.` or none.
- **Without a separator** (`MAB1234`) the code can't always be told apart from the letters. The tool lists every valid reading (`M-AB 1234`, `MA-B 1234`) and you pick one.
- A separator right after the first group of letters fixes the code: `MA-B 1234` is read as code `MA`.
- `E` (electric) and `H` (historic) are recognised as a suffix after the number.
- Batch mode: one plate per line, or separated by `,` or `;` (max. 500).

## Rules checked

| Rule | Level |
|---|---|
| Code is a known German code (*Unterscheidungszeichen*) | error |
| Special codes for authorities (e.g. `BD`, `BP`, `THW`, `Y`, `NRW`, `BYL`) and diplomatic plates (`0-…`) are not available to private persons | error |
| 1–2 letters A–Z after the code (no umlauts) | error |
| Number 1–4 digits, no leading zero | error |
| Code + letters + number ≤ 8 characters | error |
| With E/H suffix: more than 7 characters usually don't fit | warning |
| Letters `HJ`, `KZ`, `NS`, `SA`, `SS` are not issued anywhere | error |
| Letters `AH`, `HH`, `IS` | warning |
| Combinations across the hyphen, e.g. `S-S`, `K-Z`, `N-SU` | warning |
| Numbers used as extremist codes, e.g. `18`, `88`, `444`, `1488` | warning |

Which combinations are refused beyond the nationwide ban differs between states and authorities, so these rules are shown as warnings. Authorities can block further combinations.

## Output

- **Format check:** plate in standard notation, verdict and the individual checks.
- **Authority:** code, state, last logged result, one box per issuing authority with portal links.
- **Copy buttons** for the full plate and for the code, letters and number separately (most portals have one field each).
- **Check log** (CSV: `checked_at, plate, result, authority, note`; `result` is `available`, `unavailable`, `reserved` or `unclear`).
- **Batch CSV:** `input, plate, format_valid, warnings, problem, authority, state, last_result, last_checked`.
- **Backup (JSON):** log plus saved portal links. **Restore** merges a backup into the current data.

### What the portal result means

- **Available:** currently neither issued to a vehicle nor reserved at that authority.
- **Not available:** issued to a vehicle, reserved by someone, or blocked. The portals don't say which.
- The result is a snapshot. Plates that are deregistered usually become available again after a waiting period set by the authority.

## How it works

- **Parser:** the input is upper-cased, separators removed, and split into a run of letters, the digits and an optional E/H. All splits of the letters into a known code (1–3 characters) and 0–2 letters are tried. If some readings are valid, only those are offered.
- **Authority data:** the code table is embedded in the page (704 codes, 16 states). For 33 codes that are issued by both a city and the surrounding district (e.g. `M`, `A`, `KS`, `L`, `FR`, `HB`), both authorities are listed.
- **Portal links:** the tool doesn't ship a list of portal URLs, because they change often and couldn't be verified for all authorities. Instead, it builds a search for “Wunschkennzeichen reservieren &lt;authority&gt; Zulassungsstelle”. Once you have found the official portal, save it with **Save portal link**; it is then linked directly.

### Data sources and corrections

- Code → district: *Kfz-Kennzeichen Deutschland*, Senatsverwaltung für Wirtschaft, Technologie und Forschung Berlin (open data, CC BY 3.0 DE), via the npm package [`german-license-plate-prefixes`](https://github.com/derhuerst/german-license-plate-prefixes) 2.18.0 (2021).
- Current code list: npm package [`kennzeichen`](https://github.com/canida-software/kennzeichen) 0.1.6 (MIT, 2026), used to find codes introduced after 2021 and special codes.
- Manual corrections: `N` → City of Nuremberg; `EA` → Wartburgkreis (merger 2021); `HGW`, `NB`, `HST`, `HWI` → today's districts in Mecklenburg-Vorpommern; `IGB` → Saarpfalz-Kreis; `VK` → Regionalverband Saarbrücken; `WZ` → Lahn-Dill-Kreis; `BÜS` → Konstanz; `HB` → Bremen and Bremerhaven.
- Added by hand, marked **unverified** in the tool: `MÜL`, `NEU` (Breisgau-Hochschwarzwald), `OTW` (Neunkirchen), `SLG` (Sigmaringen), `STO` (Konstanz), `WG` (Ravensburg), `SÄK` (Waldshut).
- Listed in the current code list, district unknown: `SIH`, `WIN`, `WIV`, `MUC` (accepted with a warning).

## Limitations

- **No automatic availability check.** See [Is there a central database?](#is-there-a-central-database). The tool only prepares the check.
- The code table may miss codes introduced recently and may contain outdated assignments after district reforms. Unknown codes are reported as errors; check with the district if a code is new.
- The search links can also show commercial sites that look official and charge extra. Use the portal linked from the website of the district, city or state service portal.
- Germany only. Other countries' plates are reported as invalid or as a German code that happens to match.
- Motorcycle and other small plates have stricter length limits, which the tool doesn't check.

## Self-test

Click **Run tests** in the “Self-test” panel. 21 test cases check the parser (notations, suffixes, umlauts, ambiguous input), every rule, special and diplomatic plates, the integrity of the code data (size, all 16 states, shared codes, spot checks), portal URL validation, search links, CSV quoting and HTML escaping.

## Browser compatibility

Current versions of Chrome, Edge, Firefox and Safari on desktop and mobile (responsive layout, light and dark mode). Plain ES2020 without modules or libraries, so it works via `file://`. If localStorage is blocked (some private modes), the tool works but forgets the log and saved links on reload.

## Privacy

All data (input, log, saved portal links) stays in your browser's localStorage. The page makes no network requests by itself. Clicking a search or portal link opens that site in a new tab, and the search engine receives the authority name, not the plate.

## Third-party libraries and attributions

| Library / data | Version | License | Source |
|---|---|---|---|
| Kfz-Kennzeichen Deutschland (code → district) | 2021, via `german-license-plate-prefixes` 2.18.0 | CC BY 3.0 DE | Senatsverwaltung für Wirtschaft, Technologie und Forschung Berlin, daten.berlin.de |
| `kennzeichen` (code list) | 0.1.6 | MIT | <https://github.com/canida-software/kennzeichen> |

No libraries are loaded at runtime; the data is embedded in `index.html`.

## Changelog

### v0.1.0 – 2026-10-30

- Initial release: format check with ambiguity handling, issuing authority for 704 codes, portal search and saved portal links, copy buttons, check log with CSV/JSON export and restore, batch check, code lookup, light/dark mode, built-in self-test.
