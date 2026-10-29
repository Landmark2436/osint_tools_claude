# Geo Triangulator

Estimates the position, or the possible area, of an unknown target from known WGS84 points with measured **distances (radii)** and/or **bearings**, or from **coordinates alone**. The result is shown on an OpenStreetMap map together with the residuals of every measurement.

Typical use: location games such as hide and seek, where the hider leaks a position every now and then and may only move a limited distance from the hiding spot (mode 7).

**Status:** beta · **Version:** 0.3.0 · **Open:** [`index.html`](index.html)

## Quick start

**Online (recommended):** <https://landmark2436.github.io/osint_tools_claude/tools/geo-triangulator/> (once GitHub Pages is enabled for this repository).

**Offline copy:**

1. Download or clone this repository.
2. Open `tools/geo-triangulator/index.html` in a current browser (double-click; no installation, no server). Calculations work fully, but OpenStreetMap blocks the map tiles for local files (see [Limitations](#limitations)).
3. Click on the map to add points, or choose **Load example…** to see a demo.
4. Enter a radius (m) and/or a bearing (°) for each point. The result updates automatically.

An internet connection is required for the CDN libraries (Leaflet, Turf.js) and the map tiles. If the libraries cannot be loaded, the page shows an error message instead of the tool.

## Modes

| Mode | Minimum input | Result |
|---|---|---|
| **Automatic** (default) | any | Picks one of the modes below from the data and shows which one it used |
| 1 · One point with radius | 1 point with radius | Circle as possible area, area and circumference |
| 2 · Two points with radii | exactly 2 points with radius | Intersection area (lens) and both intersection points; if the circles don't meet, a notice and the point of least weighted deviation |
| 3 · Trilateration | ≥ 3 points with radius | Least-squares estimate, plus the area common to all circles (if one exists) |
| 4 · Triangulation | ≥ 2 points with bearing | Intersection of the bearing rays (least squares for > 2); parallel rays and intersections behind an observer are reported; intersection of the ±2σ bearing cones |
| 5 · Mixed | ≥ 2 measurements in total (radii + bearings) | Joint weighted adjustment; one point with radius **and** bearing already gives a position (polar fix) |
| 6 · Delaunay | ≥ 3 distinct points | Triangle mesh of the points (no target estimate); select manually |
| 7 · Coordinates only | ≥ 2 points, or 1 point + allowed distance; no radius/bearing needed | Without allowed distance: the smallest equal radius at which the circles around all points meet in one point, and that point. With allowed distance R: the possible hiding area (overlap of all R-circles), or a warning if the points are too far apart for R |

Automatic selection: radii only → mode 1/2/3 by count; bearings only → mode 4 (≥ 2 bearings); both → mode 5; neither → mode 7 (≥ 2 points, or 1 point with an allowed distance). Mode 6 is only used when selected.

### Mode 7 in hide and seek

Enter every leaked position as a point (paste or click; no radius needed).

- **Allowed distance known** (e.g. the rule “stay within 500 m of your hiding spot”): enter it in the field **Allowed distance from hiding spot** below the mode selector. The hiding spot must be within that distance of *every* leak, so it lies where all circles overlap (red area). Each new leak can only make the area smaller. If no overlap exists, the leaks contradict the rule. The warning then shows the smallest distance that would fit.
- **Allowed distance unknown:** leave the field empty. The tool shows the smallest distance that fits all leaks (a lower bound for the hider's actual allowance) and the only spot that works with it: the point whose largest distance to all leaks is as small as possible (centre of the smallest circle enclosing all leaks).

The field is stored with your other inputs and only appears when mode 7 is selected or automatic mode could choose it.

When the data is insufficient, contradictory (s₀ > 3, circles that don't intersect, rays that meet behind an observer) or ambiguous (two equally good positions), the tool says so in the result panel.

## Input

### Map and table

- **Map click** adds a point (toggle “Add point on map click”). **Drag** a marker to move it.
- **Paste coordinates** (e.g. copied from Google Maps):
  - into the “Paste coordinates” field, then Enter or **Add**
  - anywhere on the page with Ctrl+V / ⌘V, as long as no input field is focused
  - into a Lat or Lon cell of the table, which fills both cells

  Several lines create several points; unrecognised lines are reported. Accepted formats (latitude first unless hemisphere letters say otherwise):

  | Format | Example |
  |---|---|
  | Decimal degrees | `48.101440, 11.588161` · `48.101440 11.588161` · `48,101440; 11,588161` |
  | Hemisphere letters | `48.1014° N, 11.5882° E` · `N 48.1014 E 11.5882` |
  | Degrees, minutes, seconds | `48°06'05.2"N 11°35'17.4"E` |
  | Degrees, decimal minutes | `48°06.087'N 11°35.290'E` |
  | Google Maps link | `…/@48.101440,11.588161,17z` · `…?q=48.101440,11.588161` · place links with `!3d…!4d…` (the pin position is used) |
  | OpenStreetMap link | `…/#map=17/48.101440/11.588161` · `…?mlat=48.101440&mlon=11.588161` |

- **Table:** all values are editable. Columns: show/use (👁), name, latitude, longitude, radius (m), σ radius (m), bearing (°), σ bearing (°), delete.
- Hidden points (👁 unchecked) are neither shown nor used.
- Empty σ uses defaults: radius 2 % of the radius (min. 5 m), bearing 2°.
- Bearings are degrees clockwise from **true** north (0 = north, 90 = east), measured **from the point towards the target**.
- Inputs are saved automatically in the browser's localStorage and restored on the next start.

### CSV import / export

- First line is a header. Separator `,` `;` or tab (detected from the header line).
- With `;` or tab as separator a decimal comma (`48,137`) is accepted.
- Empty cells are allowed. Rows without lat/lon are skipped.

| Column (export name) | Also accepted on import | Required | Unit | Description |
|---|---|---|---|---|
| `name` | `label`, `id`, `title`, `point` | no | text | Point name |
| `lat` | `latitude`, `lat_deg`, `y` | **yes** | decimal degrees, WGS84 | Latitude (−90…90) |
| `lon` | `lng`, `long`, `longitude`, `lon_deg`, `x` | **yes** | decimal degrees, WGS84 | Longitude (−180…180) |
| `radius_m` | `radius`, `r`, `distance`, `distance_m`, `range`, `range_m`, `dist` | no | metres | Distance from the point to the target (> 0) |
| `sigma_radius_m` | `sigma_r`, `sigma_radius`, `radius_sigma`, `uncertainty_m`, `radius_uncertainty`, `sigma_m` | no | metres | Standard deviation of the radius (> 0) |
| `bearing_deg` | `bearing`, `azimuth`, `azimuth_deg`, `az`, `heading`, `direction` | no | degrees | Bearing towards the target, from true north |
| `sigma_bearing_deg` | `sigma_b`, `sigma_bearing`, `bearing_sigma`, `uncertainty_deg`, `bearing_uncertainty` | no | degrees | Standard deviation of the bearing (0…90) |
| `visible` | `show`, `enabled`, `use` | no | `true`/`false` | `false`, `0`, `no`, `n`, `hidden` hide the point |

Header names are case-insensitive. A file without a header is read as `lat,lon,radius,bearing,sigma_radius,sigma_bearing`.

Example:

```csv
name,lat,lon,radius_m,sigma_radius_m,bearing_deg,sigma_bearing_deg,visible
S1,48.165743,11.583410,3200,50,,,true
S2,48.122370,11.601840,2600,50,,,true
O1,48.151980,11.532110,,,117.5,1,true
```

### GeoJSON import / export

A `FeatureCollection` of `Point` (or `MultiPoint`) features. Point attributes are read from `properties` using the same names as the CSV columns (`name`, `radius_m`, `sigma_radius_m`, `bearing_deg`, `sigma_bearing_deg`, `visible`). Other geometry types are skipped.

## Output

- **Estimated position:** red crosshair marker. Alternative, equally good positions (for example the second intersection point) are shown in purple. Coordinates have a **Copy** button.
- **Result area:** semi-transparent red: the circle, lens, common area of all circles, or bearing-cone intersection, with its size.
- **Quality:** number of observations, redundancy, s₀ (a-posteriori standard deviation of unit weight), iterations.
- **Residuals** per measurement (computed − observed, evaluated on the sphere) with v/σ. |v/σ| > 3 is flagged in red.
- **Export result (GeoJSON):** estimate(s) with residuals and s₀, result areas and the measurement points.

## How it works

- **Local metric projection:** all calculations run in an azimuthal equidistant projection (spherical earth, R = 6 371 008.8 m) centred on the centroid of the points, in metres. After the first solution the projection is **re-centred on the estimate** and the adjustment repeated. Distances from the projection centre are exact, and great circles through it are straight lines, so radii and bearings are then modelled without projection error.
- **Bearings** are converted to plane azimuths at each observer, which compensates the meridian convergence.
- **Least squares:** a self-written Levenberg–Marquardt solver minimises Σ(v/σ)² over the two unknowns (east, north). Radius model: ‖X − Pᵢ‖. Bearing model: atan2(Δx, Δy). Start values come from closed-form constructions: linearised trilateration, pairwise circle/circle, ray/ray and ray/circle intersections, and polar fixes. Several starts are tried, so ambiguous geometries return all equally good solutions.
- **Weights:** each measurement is weighted with 1/σ², so precise measurements count more. σ also makes radii (metres) and bearings (degrees) comparable in mixed mode. s₀ = √(vᵀWv / redundancy) shows whether the measurements agree with their σ.
- **Mode 2 closed form:** circle intersection a = (r₁² − r₂² + d²)/2d, h = √(r₁² − a²). If the circles don't meet, the point of least weighted deviation lies on the centre line.
- **Mode 7:** smallest enclosing circle of the points (Welzl's algorithm) in the local projection, re-centred on its centre until stable. Distances from the projection centre are exact, so the radius is geodesically exact. Its radius is the smallest R for which all R-circles share a point.
- **Areas** (circles, intersections, bearing cones, Delaunay via `turf.tin`) are computed with Turf.js on geodesic polygons.

## Limitations

- The result can only be as good as the inputs. Wrong radii, bearings or σ values give wrong positions, and small residuals do not prove correctness.
- Spherical earth model. Accurate to the millimetre level for distances up to a few hundred kilometres; less suitable for continental distances. Not for use across the poles or the ±180° meridian.
- Map tiles and libraries need an internet connection.
- **Map tiles and `file://`:** OpenStreetMap's tile servers require an HTTP Referer, i.e. the web address of the requesting page. A file opened by double-click (`file://`) sends none, so the map shows “Access blocked” (see [osm.wiki/Blocked](https://osm.wiki/Blocked)). The page cannot add a Referer itself. Use the tool from a web address instead: the [online version on GitHub Pages](https://landmark2436.github.io/osint_tools_claude/tools/geo-triangulator/) or any web server. Opened locally, the tool shows a notice with that link. All calculations, import/export and the self-test still work without the map background.
- Two radii, or one radius plus one bearing from different points, are inherently ambiguous: two positions are reported.

## Self-test

Click **Run tests** in the “Self-test” panel. Synthetic measurements are generated from a known target, and 25 test cases check:

- the projection
- every mode (exact, noisy, contradictory and degenerate data: separate and nested circles, parallel rays, rays meeting behind an observer, ambiguity; mode 7 with equilateral/obtuse configurations, 30 km scale, allowed distance and contradiction)
- automatic mode selection
- CSV/GeoJSON round trips
- parsing of pasted coordinates (decimal, DMS, hemisphere letters, map links, invalid input)
- LM convergence from a poor start value

Each test shows passed/failed with details.

## Browser compatibility

Current versions of Chrome, Edge, Firefox and Safari on Windows, macOS and Linux, plus mobile browsers (responsive layout, light and dark mode). Plain ES2020 without modules, so it works via `file://`. No extensions or admin rights needed. If localStorage is blocked (for example in some private modes), the tool still works but doesn't remember inputs.

## Privacy

All data stays in your browser (localStorage). The only network requests are the CDN library downloads and map tiles. No tracking, no analytics.

## Third-party libraries and attributions

| Library / data | Version | License | Source |
|---|---|---|---|
| [Leaflet](https://leafletjs.com/) | 1.9.4 (pinned) | BSD-2-Clause | `https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/` |
| [Turf.js](https://turfjs.org/) | 7.1.0 (pinned) | MIT | `https://unpkg.com/@turf/turf@7.1.0/turf.min.js` |
| Map data | – | [ODbL](https://opendatacommons.org/licenses/odbl/) | © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors |
| Map tiles | – | [Tile usage policy](https://operations.osmfoundation.org/policies/tiles/) | OpenStreetMap standard tiles (default); optional: OSM Humanitarian (OSM France) |

## Changelog

### v0.3.0 – 2026-10-29

- New mode 7 “Coordinates only”: without radii or bearings, the smallest equal radius at which all circles meet and the common point (minimum enclosing circle). Optional **allowed distance** turns it into a hide-and-seek search: the possible hiding area is the overlap of all circles, and contradictions are reported.
- Automatic mode now picks mode 7 for points without radius/bearing. The Delaunay mesh (mode 6) is used only when selected.
- New example “Leaked positions”. Self-test extended to 25 cases.

### v0.2.0 – 2026-10-29

- Removed the error ellipse and the 95 % uncertainty figures from the map, the result panel and the result GeoJSON export, to keep the output simple. The position calculation is unchanged. Residuals, s₀ and the warnings for contradictory or weak geometry remain.

### v0.1.3 – 2026-10-29

- New: paste coordinates (e.g. from Google Maps) via a paste field, Ctrl+V anywhere on the page, or into a Lat/Lon cell. Supports decimal degrees, DMS, hemisphere letters and Google Maps / OpenStreetMap links; multiple lines add multiple points.
- Self-test extended to 22 cases.

### v0.1.2 – 2026-10-29

- Removed the CARTO base maps: CARTO now requires an API key.
- OpenStreetMap is the default base map again everywhere. When opened via `file://`, a notice explains why the tiles are blocked and links to the online version.

### v0.1.1 – 2026-10-29

- Fix: when opened via `file://`, the map now defaults to CARTO Voyager (OpenStreetMap data), because the OSM tile server blocks requests without a Referer (“Access blocked”). Standard OSM tiles remain the default on web hosting.
- Fix: the “No points yet” message in the empty table was cut off.
- The version number is shown in the header.

### v0.1.0 – 2026-10-29

- Initial release: modes 1–6 plus automatic mode, Levenberg–Marquardt adjustment with re-centred azimuthal equidistant projection, error ellipses and residuals, CSV/GeoJSON import and export, result export, localStorage persistence, light/dark mode, built-in self-test.
