# Phase 5: Canvas Editing — Advanced — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 05-canvas-editing-advanced
**Areas discussed:** Terrain painting model, Terrain visual feedback, Terrain undo behavior, Overlay persistence

---

## Terrain painting model

| Option | Description | Selected |
|--------|-------------|----------|
| Territory-click | Click/hover assigns terrain to territory under cursor. Per-territory, no raster math. | |
| Pixel brush stroke | Freehand stroke; backend resolves territory pixels intersecting stroke. | |
| Territory-click + brush radius | Hybrid: brush radius determines which territories within circle get painted simultaneously. | ✓ |

**User's choice:** Territory-click + brush radius

**Follow-up — Brush size:**

| Option | Description | Selected |
|--------|-------------|----------|
| Adjustable slider | Brush-size slider in terrain toolbar (1–5 territory radius). Stored in useEditorStore. | ✓ |
| Fixed radius | Hard-coded radius, simpler, one less UI element. | |

**User's choice:** Adjustable slider

---

## Terrain visual feedback

| Option | Description | Selected |
|--------|-------------|----------|
| Territory fill color | Fill switches to terrain color when terrain layer active; kingdom colors hidden. | |
| Separate hatch/icon overlay | Kingdom colors stay; hatching/icons drawn on separate layer. | |
| Both: color mode + icon badges | Fill color switches when terrain layer active; Unicode emoji badge at centroid always visible. | ✓ |

**User's choice:** Both — color mode + Unicode emoji badges

**Follow-up — Icon style:**

| Option | Description | Selected |
|--------|-------------|----------|
| Unicode/emoji badges | ⛰️🌲🌾🌊🏜️ as Konva Text nodes at centroid. Zero asset pipeline. | ✓ |
| SVG icon set | Custom SVG icons as Konva Image nodes. Better quality, requires assets. | |
| You decide | Claude picks simplest approach. | |

**User's choice:** Unicode/emoji badges

---

## Terrain undo behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, undo-tracked | Named zundo transaction per stroke: "Pintar Montanha — 3 condados". terrain_types dict diff in useProjectStore temporal. | ✓ |
| No, auto-saved only | Fire-and-forget PATCH, not in undo stack. Simpler but can't undo mis-paint. | |

**User's choice:** Yes, undo-tracked via zundo named transactions

---

## Overlay persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Ephemeral — client-side only | URL.createObjectURL() → Konva Image. Gone on reload. Zero backend work. | ✓ |
| Persisted — uploaded to server | FastAPI upload, stored in project dir, path in SQLite. Durable but adds backend endpoint. | |

**User's choice:** Ephemeral — client-side only

---

## Claude's Discretion

- Exact brush radius unit (pixels vs. geographic km)
- Terrain color palette exact hex values
- Slider range and step size for brush radius
- Emoji font/size in Konva Text badge nodes

## Deferred Ideas

- Per-territory manual terrain override via right-click context menu
- Terrain hatch/texture overlay (SVG-based, v2)
- Server-side overlay upload and persistence (v2)
- Barony-level terrain painting
