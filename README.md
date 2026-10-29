# OSINT Tools

A growing collection of small, self-contained **OSINT (open-source intelligence) tools** built with [Claude Code](https://claude.ai/code). Most tools are a single HTML file that runs in the browser, with no installation, no build step and no backend. Tools that need a backend (for example to query sites that send no CORS headers) are small Python command-line tools in their own folder.

## Available tools

| Tool | Description | Status / Version | Link |
|---|---|---|---|
| Geo Triangulator | Estimates a target's position or possible area from points with distances (radii) and/or bearings, using least squares on an OpenStreetMap map | beta · v0.1.0 | [Open](tools/geo-triangulator/index.html) · [README](tools/geo-triangulator/README.md) |
| selector-recon | Python CLI: passive lookups for email addresses, phone numbers, usernames, domains and IPs (WhatsMyName, Sherlock, Maigret, DNS, RDAP, Gravatar, HIBP, Shodan, …) with paste-ready Markdown, JSON and a self-contained HTML report | beta · v0.1.0 | [README](tools/selector-recon/README.md) · [Sample report](tools/selector-recon/samples/findings.md) |

## Usage

1. Download the repository as a ZIP or clone it: `git clone https://github.com/landmark2436/osint_tools_claude.git`
2. Browser tools: open `tools/<tool-name>/index.html` in a current browser (double-click), or open the [landing page](index.html).
3. Python tools: follow the install steps in the tool's README (a virtual environment inside the tool folder; nothing global).

Some tools load libraries from a CDN and map tiles from the internet, so they need an online connection.

**GitHub Pages (optional):** enable Pages for this repository (*Settings → Pages → Deploy from branch*, root folder). The landing page is then served at `https://<user>.github.io/<repo>/`. No changes to the files are needed.

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
        ├── index.html     browser tool: the tool (single, self-contained file)
        ├── pyproject.toml Python tool: package, with src/ and tests/ next to it
        └── README.md      tool documentation
```

## Adding a new tool

1. Create `tools/<tool-name>/` (kebab-case) containing a self-contained `index.html`.
2. Copy [`docs/TOOL_TEMPLATE.md`](docs/TOOL_TEMPLATE.md) to `tools/<tool-name>/README.md` and fill it in.
3. Add a row to the tool table above and a card to [`index.html`](index.html).
4. Commit using Conventional Commits, e.g. `feat(<tool-name>): add initial version`.

**Conventions:** each tool works standalone via `file://` where possible. Python tools keep their virtual environment, pinned requirements and tests inside their own folder. No shared code between tools. UI text, comments and docs in English. Browser tools load external libraries only via CDN with pinned versions; Python tools pin their dependencies in `requirements.txt`. No tracking or analytics. No API keys or secrets in the repository (Python tools read optional keys from environment variables). In browser tools, user data stays in the browser and is never sent to third parties (except map tile requests); Python tools send a selector only to the sources their README lists.

## Responsible use

These tools are meant for lawful research using publicly available information. You are responsible for complying with applicable laws and for respecting the privacy of others. Do not use them to stalk, harass or surveil people.

## License

[MIT](LICENSE). Third-party libraries and map data keep their own licenses (listed in each tool's README).
