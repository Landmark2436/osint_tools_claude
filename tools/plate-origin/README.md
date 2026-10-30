# Plate Origin

Shows where a German number plate comes from. Type the first letters of a plate, and while you type the page lists the matching codes (*Unterscheidungszeichen*) with the issuing city or district and the federal state. Made for a quick lookup on the phone.

**Status:** beta · **Version:** 0.2.0 · **Open:** [`index.html`](index.html)

## Quick start

**Online:** <https://landmark2436.github.io/osint_tools_claude/tools/plate-origin/> (once GitHub Pages is enabled for this repository). Tip: add it to your phone's home screen.

**Offline copy:** open `tools/plate-origin/index.html` in a browser (double-click). No libraries, no network requests; all data is in the file.

Type `FDB`, `wü`, `MU` or a whole plate such as `M-AB 1234`.

## What is shown

| Section | When | Meaning |
|---|---|---|
| Main result (highlighted) | the letters typed are a code | Issuing city or district and state |
| Or, if the code is shorter | no separator typed | Without a hyphen, `MAB` could also be `MA-B…` or `M-AB…`. The rest would be the plate letters (1–2). |
| Codes starting with … | still typing (1–2 letters, no digits) | Longer codes that begin with what you typed |

- A separator (`-`, space) after the letters fixes the code: `M-AB 1234` shows only `M`.
- Digits right after the letters (`MAB1234`): real plates always have 1–2 letters after the code, so only shorter codes are listed.
- Umlauts can be typed as plain letters: `MU` shows `MU` (Munich district) and `MÜ` (Mühldorf).
- Codes used by both a city and the surrounding district (e.g. `M`, `A`, `KS`, `L`) list both.
- Special codes (federal and state authorities, Bundeswehr `Y`, THW, NATO `X`) are shown as such.
- The input is kept in the address (`…/index.html#FDB`), so a lookup can be bookmarked or shared.

## Data

706 codes in 16 states, plus 19 special codes. Old codes reintroduced since 2012 (e.g. `FDB`, `WOL`) are shown with the district that issues them today.

- Code → district: *Kfz-Kennzeichen Deutschland*, Senatsverwaltung für Wirtschaft, Technologie und Forschung Berlin (open data, CC BY 3.0 DE), via the npm package [`german-license-plate-prefixes`](https://github.com/derhuerst/german-license-plate-prefixes) 2.18.0 (2021).
- Current code list: npm package [`kennzeichen`](https://github.com/canida-software/kennzeichen) 0.1.6 (MIT, 2026), for codes introduced after 2021 and special codes.
- Manual corrections: `N` → City of Nuremberg; `EA` → Wartburgkreis (merger 2021); `HGW`, `NB`, `HST`, `HWI` → today's districts in Mecklenburg-Vorpommern; `IGB` → Saarpfalz-Kreis; `VK` → Regionalverband Saarbrücken; `WZ` → Lahn-Dill-Kreis; `BÜS` → Konstanz; `HB` → Bremen and Bremerhaven.
- Added by hand, marked **unverified**: `MÜL`, `NEU` (Breisgau-Hochschwarzwald), `OTW` (Neunkirchen), `SLG` (Sigmaringen), `STO` (Konstanz), `WG` (Ravensburg), `SÄK` (Waldshut), `MUC` (City of Munich), `MU` (Munich district, since January 2026).
- In use, district not known here: `SIH`, `WIN`, `WIV`.

## Limitations

- Codes introduced very recently may be missing, and assignments can be outdated after district reforms.
- The page shows the issuing authority of the code, not where the vehicle actually is or who owns it. A plate keeps its code when the owner moves within the same district, and since 2015 also when moving to another district.
- Germany only.

## Self-test

Click **Self-test** at the bottom of the page. 11 checks cover exact codes, completions while typing, whole plates with and without separator, umlauts, unknown and special codes, data integrity (16 states, no duplicate codes) and HTML escaping.

## Browser compatibility

Current Chrome, Edge, Firefox and Safari, mobile first, light and dark mode follow the system. Plain ES2020 without modules, so it works via `file://`.

## Privacy

Nothing is stored and nothing is sent anywhere. The page makes no network requests.

## Third-party libraries and attributions

| Library / data | Version | License | Source |
|---|---|---|---|
| Kfz-Kennzeichen Deutschland (code → district) | 2021, via `german-license-plate-prefixes` 2.18.0 | CC BY 3.0 DE | Senatsverwaltung für Wirtschaft, Technologie und Forschung Berlin, daten.berlin.de |
| `kennzeichen` (code list) | 0.1.6 | MIT | <https://github.com/canida-software/kennzeichen> |

No libraries are loaded at runtime; the data is embedded in `index.html`.

## Changelog

### v0.2.0 – 2026-10-30

- Renamed from *License Plate Checker* and reduced to the lookup: type letters, see codes, issuing city or district and state while typing. Removed the format check, availability portal links, check log, batch check and backup.
- Umlauts can be typed as plain letters. The input is kept in the page address.

### v0.1.1 – 2026-10-30

- New code `MU` (Munich district, since January 2026); `MUC` is now assigned to the City of Munich.

### v0.1.0 – 2026-10-30

- Initial release as *License Plate Checker* with format check, portal search, check log and batch check.
