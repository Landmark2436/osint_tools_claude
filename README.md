# OSINT Tools

A growing collection of small, self-contained **OSINT (open-source intelligence) tools** built with [Claude Code](https://claude.ai/code). Every tool is a single HTML file that runs in the browser. No installation, no build step, no backend.

## Available tools

| Tool | Description | Status / Version | Link |
|---|---|---|---|
| Geo Triangulator | Estimates a target's position or possible area from points with distances (radii) or leaked positions within an allowed distance (e.g. hide and seek), on an OpenStreetMap map | beta · v0.4.0 | [Open](tools/geo-triangulator/index.html) · [README](tools/geo-triangulator/README.md) |
| Plate Origin | Shows where a German number plate comes from: type the first letters and see the issuing city or district and the federal state while typing | beta · v0.2.0 | [Open](tools/plate-origin/index.html) · [README](tools/plate-origin/README.md) |
| IP & Domain Lookup | Reverse DNS, network owner and the domains seen on an IP; current DNS records, registration and IP history of a domain, from free public sources without API keys | experimental · v0.1.0 | [Open](tools/ip-domain-lookup/index.html) · [README](tools/ip-domain-lookup/README.md) |

## Usage

1. Download the repository as a ZIP or clone it: `git clone https://github.com/landmark2436/osint_tools_claude.git`
2. Open `tools/<tool-name>/index.html` in a current browser (double-click), or open the [landing page](index.html).

Some tools load libraries from a CDN and map tiles from the internet, so they need an online connection. **Map tools:** OpenStreetMap blocks map tiles for pages opened as local files (`file://`), so use the GitHub Pages version for them.

**GitHub Pages:** enable Pages for this repository (*Settings → Pages → Deploy from branch*, root folder). The landing page is then served at <https://landmark2436.github.io/osint_tools_claude/>. No changes to the files are needed.

## Repository structure

```text
/
├── README.md              this file
├── index.html             landing page linking to all tools
├── LICENSE
├── docs/
│   └── TOOL_TEMPLATE.md   README template for new tools
└── tools/
    └── <tool-name>/       one folder per tool, kebab-case
        ├── index.html     the tool (single, self-contained file)
        └── README.md      tool documentation
```

## Adding a new tool

1. Create `tools/<tool-name>/` (kebab-case) containing a self-contained `index.html`.
2. Copy [`docs/TOOL_TEMPLATE.md`](docs/TOOL_TEMPLATE.md) to `tools/<tool-name>/README.md` and fill it in.
3. Add a row to the tool table above and a card to [`index.html`](index.html).
4. Commit using Conventional Commits, e.g. `feat(<tool-name>): add initial version`.

**Conventions:** each tool works standalone via `file://` where possible. No shared code between tools. UI text, comments and docs in English. External libraries only via CDN with pinned versions. No tracking, analytics, API keys or secrets. User data stays in the browser and is never sent to third parties (except map tile requests, and the queries of the IP & Domain Lookup, which by design asks public sources and says so in its README).

## Responsible use

These tools are meant for lawful research using publicly available information. You are responsible for complying with applicable laws and for respecting the privacy of others. Do not use them to stalk, harass or surveil people.

## License

[MIT](LICENSE). Third-party libraries and map data keep their own licenses (listed in each tool's README).
