<!--
  README template for a new tool.
  1. Copy this file to tools/<tool-name>/README.md (folder name in kebab-case).
  2. Replace every {{PLACEHOLDER}} and delete sections marked "optional" that do not apply.
  3. Keep the section order so all tool READMEs look the same.
-->

# {{TOOL_NAME}}

{{ONE_OR_TWO_SENTENCES: what the tool does and for whom.}}

**Status:** {{experimental | beta | stable}} · **Version:** {{0.1.0}} · **Open:** [`index.html`](index.html)

## Quick start

1. Download or clone this repository.
2. Open `tools/{{tool-name}}/index.html` in a current browser (double-click; no installation, no server).
3. {{FIRST_ACTION, e.g. "Click on the map to add a point."}}

{{REQUIREMENTS, e.g. "An internet connection is required for the CDN libraries and map tiles."}}

## Modes / features

| {{Mode / feature}} | {{Minimum input}} | {{Result}} |
|---|---|---|
| {{…}} | {{…}} | {{…}} |

## Input

### {{Input method 1, e.g. manual entry}}

{{Description.}}

### File import (optional)

{{Supported formats.}}

| Column | Required | Unit / format | Description |
|---|---|---|---|
| `{{column}}` | {{yes/no}} | {{unit}} | {{…}} |

Example:

```csv
{{header}}
{{row}}
```

## Output

- {{What is shown and what can be exported.}}

## How it works

{{Short explanation of the method / algorithm. Link to sources where useful.}}

## Limitations

- {{Known limits of accuracy, data, environment.}}

## Self-test (optional)

{{How to run the built-in tests and what they check.}}

## Browser compatibility

{{Tested browsers / minimum versions; file:// notes.}}

## Privacy

All data stays in your browser. {{List any network requests the tool makes, e.g. map tiles or CDN libraries.}}

## Third-party libraries and attributions

| Library / data | Version | License | Source |
|---|---|---|---|
| {{name}} | {{x.y.z (pinned)}} | {{license}} | {{CDN URL}} |

## Changelog

### v{{0.1.0}} – {{YYYY-MM-DD}}

- Initial release.
