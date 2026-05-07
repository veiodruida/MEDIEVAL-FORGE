# Phase 2: Read-Only Canvas Viewer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 02-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** 02-read-only-canvas-viewer
**Areas discussed:** Visual style & color coding, Inspector panel layout & content, Layer toggle UX & label behavior, Navigation & viewport behavior

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Visual style & color coding | Hierarchy colors, border stroke, capital marker, selection highlight | ✓ |
| Inspector panel layout & content | Panel placement, property groups, empty state | ✓ |
| Layer toggle UX & label behavior | Panel home, defaults, zoom threshold, label text | ✓ |
| Navigation & viewport behavior | Initial view, zoom limits, shortcuts, wheel anchor | ✓ |

---

## Visual Style & Color Coding

### How should territories be colored?

| Option | Description | Selected |
|--------|-------------|----------|
| Generator-assigned colors (Recommended) | Read from lookup_condado_colors.json / lookup_barony_colors.json — guarantees parity with PNG previews | ✓ |
| Per-kingdom palette at runtime | Hue per kingdom, vary saturation/lightness by duchy | |
| Fixed hierarchy-level palette | One color per hierarchy level (kingdoms=gold, duchies=blue…) | |

**User's choice:** Generator-assigned colors
**Notes:** Avoids palette drift between canvas and exported Unity assets.

### Primary colored fill level by default

| Option | Description | Selected |
|--------|-------------|----------|
| Condado (Recommended) | Main game unit; matches lookup_condado.png | ✓ |
| Barony | Finest detail; condados via thicker borders | |
| User picks via layer toggle | No default primary | |

**User's choice:** Condado

### Selection highlight

| Option | Description | Selected |
|--------|-------------|----------|
| Thicker bright border + preserve fill (Recommended) | 2–3 px gold/yellow stroke on top of existing fill | ✓ |
| Lighten fill + thin border | Fill +20% lightness with subtle outline | |
| Dark overlay on unselected | Dim non-selected; selected stands out by contrast | |

**User's choice:** Thicker bright border + preserve fill

### Capital rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Small filled circle + ring (Recommended) | 6–8 px circle with white/dark ring outline | ✓ |
| Crown/star icon | Thematic but SVG asset mgmt + scaling issues | |
| Labeled dot | Dot + persistent city name; clutter risk | |

**User's choice:** Small filled circle with ring

---

## Inspector Panel Layout & Content

### Panel home

| Option | Description | Selected |
|--------|-------------|----------|
| Right sidebar, always visible (Recommended) | Fixed 320–360 px; empty-state copy when nothing selected | ✓ |
| Collapsible right drawer | Hidden until click; slides out | |
| Floating overlay near cursor | Popover anchored to centroid | |

**User's choice:** Right sidebar, always visible

### Property groups (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| Core identity (name, type, hierarchy path) | Name, level, parent path | ✓ |
| Geometry stats (area km², vertex count, centroid) | Area, vertex count, centroid lat/lng | ✓ |
| Capital info (city name + coords) | Capital name + coords or "No capital" | ✓ |
| Neighbors list (clickable) | Adjacent territories as chips | ✓ |

**User's choice:** All four selected

### Empty state content

| Option | Description | Selected |
|--------|-------------|----------|
| Project summary (Recommended) | Project name, totals, period, country | ✓ |
| Hint copy only | "Click a territory to inspect" | |
| Layer toggles merged in | Empty state = layer control panel | |

**User's choice:** Project summary

---

## Layer Toggle UX & Label Behavior

### Layer toggle home

| Option | Description | Selected |
|--------|-------------|----------|
| Top-left floating card over canvas (Recommended) | Radix Card overlay with 5 checkboxes | ✓ |
| Inside right inspector panel | Stacked above selected-territory info | |
| Top toolbar above canvas | Horizontal toolbar row | |

**User's choice:** Top-left floating card

### Default layers ON at first open

| Option | Description | Selected |
|--------|-------------|----------|
| All except labels (Recommended) | Terrain + Territories + Borders + Capitals ON; Labels OFF | ✓ |
| Everything ON incl. labels | Max info but collisions at fit-to-view | |
| Minimal: Territories + Borders only | Vector feel but less informative | |

**User's choice:** All except labels

### Label appearance trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Hard zoom threshold, 1 tier (Recommended) | All condado labels show at scale ≥ threshold | ✓ |
| Tiered by hierarchy | Kingdoms early, baronies late | |
| Smart by polygon size | Show if bbox > N px on screen | |

**User's choice:** Hard zoom threshold, 1 tier

### Label text content

| Option | Description | Selected |
|--------|-------------|----------|
| Territory name only (Recommended) | Just the name | ✓ |
| Name + hierarchy level | e.g., "Coruña (Condado)" | |
| Name + capital city | e.g., "Coruña / A Coruña" | |

**User's choice:** Territory name only

---

## Navigation & Viewport Behavior

### Initial view on project open

| Option | Description | Selected |
|--------|-------------|----------|
| Auto fit-to-view on load (Recommended) | Compute bbox, scale+center to fit with padding | ✓ |
| Native 1:1 | Map pixel = screen pixel, centered | |
| Remember last viewport per project | Persist in SQLite per project | |

**User's choice:** Auto fit-to-view on load

### Zoom limits & pan bounds

| Option | Description | Selected |
|--------|-------------|----------|
| Min=fit-to-view, Max=4×; pan clamped (Recommended) | Cannot zoom out past fit; cannot zoom in past 4×; pan clamped to bounds | ✓ |
| Loose: 0.25×–10×, free pan | Wide range, no clamping | |
| Strict: 1× fit only, max 3× | Never zoom out past fit | |

**User's choice:** Min=fit-to-view, Max=4×; pan clamped

### Keyboard shortcuts in Phase 2

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: Esc deselect, Ctrl+0 fit (Recommended) | Two shortcuts; avoids Phase 4 edit conflicts | ✓ |
| Full navigation set | Esc, Ctrl+0, Ctrl+/-, arrow pan | |
| No shortcuts | Mouse-only; defer all keyboard to Phase 4 | |

**User's choice:** Minimal: Esc deselect, Ctrl+0 fit-to-view

### Wheel zoom anchor

| Option | Description | Selected |
|--------|-------------|----------|
| Zoom to cursor position (Recommended) | Standard map UX; point under cursor stays under cursor | ✓ |
| Zoom to canvas center | Symmetric zoom around center | |

**User's choice:** Zoom to cursor position

---

## Claude's Discretion

- Exact zoom threshold value for labels (derive from Iberia fit-to-view math)
- Exact zoom-in max multiplier and fit-to-view padding percentage
- Font family/size and label anti-collision strategy
- Baronies rendering style when toggled ON
- Right-sidebar exact width within 320–360 px
- `react-konva`/`konva` exact version pin within the 19.x/9.x lines
- Internal Konva Stage layer architecture (3 vs 4–5 layers)
- GeoJSON loading/caching pattern via TanStack Query

## Deferred Ideas

- Persist last viewport per project (reconsider post-UAT)
- Full keyboard navigation set (Phase 4 alongside edit shortcuts)
- Multi-select (out of scope for read-only)
- Minimap (v2 Requirement per REQUIREMENTS.md)
- Tiered label zoom / smart label filtering (rejected for single threshold)
- Crown/star capital icons (rejected for dot+ring)
- Mobile/small-screen responsive layout (out of scope — desktop only)
