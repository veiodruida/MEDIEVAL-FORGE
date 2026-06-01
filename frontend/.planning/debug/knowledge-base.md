# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## 08.3-11-pen-preapply-manipulate-uat — PenShapeManipulateLayer drag no-op in UAT
- **Date:** 2026-06-01
- **Error patterns:** dLat=0, dLon=0, drag no-op, geoToStageXY, vertex drag unchanged, body drag unchanged, onMouseMove layer, draggable, React-controlled x y prop, e.target.x, pointerCanvasPos, BezierApplyControls hidden, activeTerritoryId null, LayerTogglePanel blocking
- **Root cause:** Five compounding bugs: (1) spec geoToStageXY ignores stage pan/zoom — drag anchors miss the rendered shape; (2) PenShapeManipulateLayer used Layer onMouseMove/Up which only fires from bubbled child events — once cursor leaves the shape, Stage swallows move/up → drag is a no-op; (3) Vertex Circle has React-controlled x/y props that fight Konva drag so e.target.x() at dragEnd returns start position (same class as BezierEditLayer UAT-fix#1); (4) LayerTogglePanel (always-visible top-left DOM panel) covered vertex handles after a north body drag; (5) BezierApplyControls only renders when activeTerritoryId!=null — invisible before __forgeSelectBarony() is called.
- **Fix:** (1) Add __forgePendingRingScreen() hatch to CanvasViewer; re-read before every gesture. (2) Switch PenShapeManipulateLayer to Konva draggable + onDragStart/Move/End. (3) Vertex drag: use stage.getRelativePointerPosition() (pointerCanvasPos) — immune to React prop reset; track last pointer pos in vertexLastCanvasPosRef for dragEnd. (4) Body drag direction SOUTH to stay below LayerTogglePanel. (5) Call __forgeSelectBarony(anyBaronyId) before clicking Apply. (6) Add dragCancelledRef so Esc-then-release does NOT commit (Konva fires onDragEnd after Esc). (7) Add __forgePendingOpType hatch for op-type assertions.
- **Files changed:** src/components/canvas/PenShapeManipulateLayer.tsx, src/components/canvas/__tests__/PenShapeManipulateLayer.test.tsx, src/components/canvas/CanvasViewer.tsx, tests/uat/playwright/08.3-pen-preapply-manipulate.spec.ts
---

