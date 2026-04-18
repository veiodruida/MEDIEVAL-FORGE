---
phase: 02-read-only-canvas-viewer
plan: 05
type: execute
wave: 1
depends_on: [02-01, 02-02, 02-03, 02-04]
gap_closure: true
closes_gaps: [GAP-04, GAP-05, GAP-06, GAP-07, GAP-08]
files_modified:
  - frontend/src/components/canvas/CanvasViewer.tsx
  - frontend/src/components/canvas/DecorationsLayer.tsx
  - frontend/src/components/canvas/LayerTogglePanel.tsx
  - frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx
  - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx
  - frontend/src/components/canvas/__tests__/CanvasViewer.resize.test.tsx
  - frontend/src/pages/ProjectDetail.tsx
  - frontend/src/pages/__tests__/ProjectDetail.errorBoundary.test.tsx
  - frontend/src/hooks/useZoomPan.ts
  - frontend/package.json
  - frontend/package-lock.json
autonomous: false
requirements: [CANVAS-01, CANVAS-02, CANVAS-03, CANVAS-04, CANVAS-05, CANVAS-06]

must_haves:
  truths:
    - "Canvas Stage fills the entire central viewport region regardless of browser size — resizing or zooming the viewport recomputes Stage dimensions AND minScale (closes GAP-05)"
    - "After GAP-05 lands, clicking any visible condado selects it (gold 3px outline in InteractionLayer + InspectorSidebar shows all 4 property groups) — no 'blank' regression on clicks (closes GAP-06 as verification)"
    - "Frontend renders real condado fills from condado_colors.json end-to-end against a real generated Iberia project — root cause of the #666666 fallback is diagnosed and fixed (closes GAP-04)"
    - "InspectorSidebarWrapper throw-scenario renders a visible ErrorBoundary fallback ('Sidebar failed to load — check console') instead of blanking the sidebar (closes GAP-07)"
    - "Labels checkbox has a Radix Tooltip explaining the zoom threshold; at ≥1.5× minScale labels render; DecorationsLayer test updated to assert the new 1.5 threshold (closes GAP-08)"
  artifacts:
    - path: "frontend/src/components/canvas/CanvasViewer.tsx"
      provides: "Canvas viewer with ResizeObserver-driven Stage sizing; viewportW/viewportH are useState; fitToView re-runs on dimension change to recompute minScale"
      contains: "new ResizeObserver"
    - path: "frontend/src/pages/ProjectDetail.tsx"
      provides: "Canvas region with viewport-relative height (calc) + ErrorBoundary wrapping InspectorSidebarWrapper"
      contains: "ErrorBoundary"
    - path: "frontend/src/components/canvas/DecorationsLayer.tsx"
      provides: "Label gate at 1.5× minScale (lowered from 2.0× per GAP-08 UAT hint)"
      contains: "LABEL_ZOOM_THRESHOLD_RELATIVE = 1.5"
    - path: "frontend/src/components/canvas/LayerTogglePanel.tsx"
      provides: "Radix Tooltip on the Labels row explaining 'Zoom in 1.5× to show labels'"
      contains: "Tooltip"
    - path: "frontend/src/components/canvas/__tests__/CanvasViewer.resize.test.tsx"
      provides: "Vitest covering ResizeObserver-triggered minScale recompute"
      contains: "ResizeObserver"
    - path: "frontend/src/pages/__tests__/ProjectDetail.errorBoundary.test.tsx"
      provides: "Vitest mounting ProjectDetail with a throwing useCanvasArtifacts and asserting fallback text renders"
      contains: "Sidebar failed to load"
  key_links:
    - from: "CanvasViewer.tsx wrapping div"
      to: "Stage dimensions via useState"
      via: "new ResizeObserver observing containerRef"
      pattern: "new ResizeObserver"
    - from: "ProjectDetail.tsx canvas-region Flex"
      to: "viewport-relative height"
      via: "inline style with calc(100vh - <N>px) + minHeight"
      pattern: "calc\\(100vh|minHeight"
    - from: "LayerTogglePanel.tsx Labels row"
      to: "Radix Tooltip with threshold text"
      via: "@radix-ui/themes Tooltip wrapping the Checkbox + Text"
      pattern: "Tooltip"
    - from: "ProjectDetail.tsx InspectorSidebarWrapper"
      to: "ErrorBoundary wrapper with visible fallback"
      via: "react-error-boundary"
      pattern: "ErrorBoundary|react-error-boundary"
    - from: "DecorationsLayer.tsx"
      to: "lowered label threshold"
      via: "LABEL_ZOOM_THRESHOLD_RELATIVE constant"
      pattern: "LABEL_ZOOM_THRESHOLD_RELATIVE\\s*=\\s*1\\.5"
---

<objective>
Close the five gaps opened by the human re-test on 2026-04-18 after plan 02-04 shipped. Keystone: GAP-05 (Stage hardcoded to 800×600) — once fixed, GAP-06 is resolved as a downstream symptom. GAP-04 (every condado renders `#666666` against the real Iberia pipeline) requires diagnosis before fix because the 02-04 synthetic integration test passes while the real pipeline fails — a single fix cannot be prescribed. GAP-08 and GAP-07 are deterministic UX/defensive fixes.

Purpose: Unblock the remaining FAILED/BLOCKED items in `02-HUMAN-UAT.md` (items 3, 4, 5, 6, 8, 9 all gated by GAP-05; item 1 gated by GAP-04; item 7 gated by GAP-08) so Phase 2 can actually close. This plan has an `autonomous: false` diagnostic task — the executor MUST pause after Task 2 for human-provided curl output before choosing which branch of Task 3 to apply.

Output: CanvasViewer wired to a ResizeObserver, ProjectDetail with viewport-relative canvas region + ErrorBoundary around InspectorSidebarWrapper, label threshold lowered to 1.5× with a Radix Tooltip, diagnosis committed to the plan's `<diagnosis>` block, and the branch-matching GAP-04 fix landed. D-04 (`lib/map_generator.py` black-box) preserved unless GAP-04 root cause is traced there, in which case the fix MUST stay in the service layer.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/02-read-only-canvas-viewer/02-CONTEXT.md
@.planning/phases/02-read-only-canvas-viewer/02-HUMAN-UAT.md
@.planning/phases/02-read-only-canvas-viewer/02-VERIFICATION.md
@.planning/phases/02-read-only-canvas-viewer/02-UI-SPEC.md
@.planning/phases/02-read-only-canvas-viewer/02-04-e2e-pipeline-fix-PLAN.md
@frontend/src/components/canvas/CanvasViewer.tsx
@frontend/src/components/canvas/DecorationsLayer.tsx
@frontend/src/components/canvas/LayerTogglePanel.tsx
@frontend/src/pages/ProjectDetail.tsx
@frontend/src/hooks/useZoomPan.ts
@frontend/src/hooks/useCanvasArtifacts.ts
@frontend/src/test-setup.ts
@backend/medieval_forge/services/territories_geojson.py
@backend/medieval_forge/services/generator.py

<interfaces>
<!-- Current CanvasViewer sizing (the bug) -->
<!-- CanvasViewer.tsx:58 — default props width=800, height=600 -->
<!-- CanvasViewer.tsx:219-220 — const viewportW = width; const viewportH = height (LOCALS, not state) -->
<!-- CanvasViewer.tsx:233-236 — Stage width={viewportW} height={viewportH} with NO ResizeObserver -->
<!-- CanvasViewer.tsx:225-232 — wrapping div with style={width: viewportW, height: viewportH} -->
<!-- ProjectDetail.tsx:131 — Flex mb="4" style={{ height: '600px', borderRadius: 8, overflow: 'hidden' }} -->
<!-- ProjectDetail.tsx:136 — <CanvasViewer projectId={project.id} /> — NO dimension props -->
<!-- ProjectDetail.tsx:142 — <InspectorSidebarWrapper projectId={project.id} project={project} /> — NO ErrorBoundary -->

<!-- Pre-canvas block measurement (ProjectDetail.tsx:104-127) -->
<!-- Box p="6"    → ~24px top padding -->
<!-- Flex (Heading + button) mb="4"  → ~32 + 16 = ~48px -->
<!-- Card (progress row with 10px dots) mb="4" → ~48 + 16 = ~64px -->
<!-- Total pre-canvas block ≈ 136-180px; Flex itself carries mb="4" ≈ 16px -->
<!-- Recommended: calc(100vh - 220px) minHeight: 500px — measured from lines 105-127 -->
<!-- Tune if cramped; MUST fit the success-criteria viewport on a 1080p display -->

<!-- Existing useZoomPan pan-clamp pattern (useZoomPan.ts:17-39) -->
<!-- applyPanClamp reads stage.width() / stage.height() at call time, so it -->
<!-- naturally picks up new Stage dimensions once we call it on resize. -->

<!-- test-setup.ts:6-13 already stubs ResizeObserver (observe/unobserve/disconnect). -->
<!-- For the resize test we must install a more capable fake via vi.stubGlobal that -->
<!-- captures the callback + element and lets tests invoke it synchronously. -->

<!-- DecorationsLayer.test.tsx:107-108 asserts `expect(LABEL_ZOOM_THRESHOLD_RELATIVE).toBe(2.0)` — MUST flip to 1.5. -->

<!-- Radix Tooltip import (@radix-ui/themes 3.x) -->
import { Tooltip } from '@radix-ui/themes'
<Tooltip content="Zoom in 1.5× to show labels">
  <Flex align="center" gap="2">
    <Checkbox ... />
    <Text size="2">Labels</Text>
  </Flex>
</Tooltip>

<!-- react-error-boundary is NOT currently in package.json — install required. -->
<!-- API: -->
import { ErrorBoundary } from 'react-error-boundary'
<ErrorBoundary
  fallback={<Callout.Root color="red"><Callout.Text>Sidebar failed to load — check console</Callout.Text></Callout.Root>}
>
  <InspectorSidebarWrapper projectId={project.id} project={project} />
</ErrorBoundary>

<!-- Backend files to inspect for GAP-04 diagnosis — NO EDITS in this task. -->
<!-- backend/medieval_forge/services/territories_geojson.py — emit_territories_from_disk (sidecar emit) -->
<!-- backend/medieval_forge/services/generator.py:63-76 — whitelist (both sidecars present post-02-04) -->
<!-- backend/medieval_forge/services/generator.py:~296-357 — _run_pipeline_sync real emitter call site -->
<!-- D-04: lib/map_generator.py MUST NOT be edited by any task. -->
</interfaces>
</context>

<diagnosis>
<!-- POPULATED by Task 2 (checkpoint:human-action). The executor will edit this -->
<!-- block in-place with the curl output + key-overlap results before Task 3    -->
<!-- fires. Leave as placeholder until that task runs.                           -->

TBD — will be filled in after Task 2 runs against a real generated Iberia project.

Findings will include:
- Status + body (first 500 chars) of `GET /api/projects/{id}/preview/condado_colors.json`
- Sample feature ids from `GET /api/projects/{id}/preview/territories.geojson`
- Key overlap count between the two files
- Which hypothesis (H1/H2/H3/H4) the evidence supports

Once filled in, Task 3's action block executes the branch matching the diagnosis.
</diagnosis>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wire ResizeObserver in CanvasViewer + set viewport-relative canvas region in ProjectDetail (GAP-05 keystone)</name>
  <files>frontend/src/components/canvas/CanvasViewer.tsx, frontend/src/pages/ProjectDetail.tsx, frontend/src/components/canvas/__tests__/CanvasViewer.resize.test.tsx</files>

  <read_first>
    - frontend/src/components/canvas/CanvasViewer.tsx (ENTIRE file — hook order matters; the current const viewportW/H at 219-220 must move above the early returns so hooks at the top never reorder)
    - frontend/src/pages/ProjectDetail.tsx (lines 103-145 specifically; line 131 is the hardcoded 600px, line 136 is the CanvasViewer mount site, line 142 is the InspectorSidebarWrapper we'll touch in Task 5)
    - frontend/src/hooks/useZoomPan.ts (applyPanClamp already reads stage.width()/height() at call time — ResizeObserver triggering fitToView will naturally re-clamp)
    - frontend/src/test-setup.ts (the existing ResizeObserver stub — we'll need a more capable fake in the new resize test only)
    - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx (mock patterns for TanStack Query + useUIStore; mirror these in the new resize test)
  </read_first>

  <behavior>
    - Test R1 (new file CanvasViewer.resize.test.tsx): when the container's ResizeObserver callback fires with a larger contentRect, the Stage `width`/`height` props update to the new measurements (assert via react-konva mock capturing Stage props).
    - Test R2 (same file): when the ResizeObserver callback fires with different dimensions, `computeFitToView` is called again so minScale reflects the new Stage size. Assert by spying on the projection library OR by verifying `minScale` state (exposed via data-testid on the wrapper or by asserting Stage scaleX prop after resize).
    - Test R3 (regression — existing CanvasViewer.test.tsx): tests mounting `<CanvasViewer projectId="..." />` WITHOUT width/height props still work — initial useState defaults of 800/600 preserve the test fallback. Existing 86/86 vitest suite MUST remain green.
    - Test R4 (human-visual after landing): loading `/projects/:id` on a 1920×1080 viewport shows the Stage filling the full central column between LayerTogglePanel and InspectorSidebar — no navy dead zone.
  </behavior>

  <action>
    **Edit 1 — `frontend/src/components/canvas/CanvasViewer.tsx`** (the BOTH-files advisor callout). Rework the component so hooks run unconditionally before the early returns, convert viewport dims to state, and wire a ResizeObserver. Concrete skeleton:

    ```tsx
    import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
    // ... existing imports unchanged ...

    export function CanvasViewer({ projectId, width = 800, height = 600 }: CanvasViewerProps) {
      const stageRef = useRef<Konva.Stage | null>(null)
      const containerRef = useRef<HTMLDivElement | null>(null)

      // MUST be declared BEFORE any conditional early returns (React Hook rules).
      // width/height props are the fallback for tests that mount CanvasViewer
      // directly outside a flex parent (keeps existing 86 tests green).
      const [viewportW, setViewportW] = useState<number>(width)
      const [viewportH, setViewportH] = useState<number>(height)

      const [projection, setProjection] = useState<ProjectionConfig | null>(null)
      const [minScale, setMinScale] = useState(1)
      const [currentScale, setCurrentScale] = useState(1)

      const layerVisibility = useUIStore((s) => s.layerVisibility)
      const selectedId = useUIStore((s) => s.selectedTerritoryId)
      const select = useUIStore((s) => s.select)

      const [territoriesQ, baroniesQ, condadoColorsQ, , metaQ] = useCanvasArtifacts(
        projectId,
        projection,
      )

      // ResizeObserver — measures the containerRef div. MUST NOT observe a div
      // whose size is driven by viewportW/viewportH state or we get a feedback
      // loop. The wrapping div below uses width:'100%', height:'100%' so its
      // size comes from the flex parent in ProjectDetail.
      useEffect(() => {
        const el = containerRef.current
        if (!el) return
        const ro = new ResizeObserver((entries) => {
          for (const entry of entries) {
            const cr = entry.contentRect
            // Guard against 0-size transient measurements (can happen during mount)
            if (cr.width > 0 && cr.height > 0) {
              setViewportW(Math.floor(cr.width))
              setViewportH(Math.floor(cr.height))
            }
          }
        })
        ro.observe(el)
        return () => ro.disconnect()
      }, [])

      // Build projection once metadata loads (unchanged logic)
      useEffect(() => {
        if (metaQ.data && !projection) {
          const [mapW, mapH] = metaQ.data.map_size
          const { bounds } = metaQ.data
          setProjection(
            buildProjectionConfig(
              {
                lonMin: bounds.lon_min,
                lonMax: bounds.lon_max,
                latMin: bounds.lat_min,
                latMax: bounds.lat_max,
              },
              mapW,
              mapH,
            ),
          )
        }
      }, [metaQ.data, projection])

      // fitToView reads stage.width()/height() — those are now bound to
      // viewportW/H via the Stage props below, so fitToView recomputes correctly.
      const fitToView = useCallback(() => {
        const stage = stageRef.current
        if (!stage || !projection) return
        const { scale, x, y } = computeFitToView(
          projection.mapW,
          projection.mapH,
          stage.width(),
          stage.height(),
          PADDING_PCT,
        )
        stage.scale({ x: scale, y: scale })
        stage.position({ x, y })
        setMinScale(scale)
        setCurrentScale(scale)
        stage.batchDraw()
      }, [projection])

      // D-12: auto-fit once projection lands AND whenever Stage dimensions change.
      // Adding viewportW/H to the dep array re-runs fit on resize so minScale
      // reflects the new viewport (prevents stale-minScale after browser resize).
      useEffect(() => {
        if (projection) fitToView()
      }, [projection, fitToView, viewportW, viewportH])

      useKeyboardShortcuts(fitToView)

      // ...rest of hooks (pan-on-select useEffect, wheel handler, dragBound) unchanged...

      // EARLY RETURNS — now safe because every hook above has been called.
      if (metaQ.isPending) {
        return <div ref={containerRef} style={{ width: '100%', height: '100%' }}>Loading map…</div>
      }
      if (metaQ.error) { /* ... existing messages, wrap in containerRef div same pattern ... */ }
      if (!metaQ.data || !projection || !territoriesQ.data || !condadoColorsQ.data || !baroniesQ.data) {
        return <div ref={containerRef} style={{ width: '100%', height: '100%' }}>Loading map…</div>
      }

      const terrainSrc = `/api/projects/${projectId}/preview/terrain.png`

      return (
        <ProjectionProvider value={projection}>
          <div
            ref={containerRef}
            style={{
              position: 'relative',
              width: '100%',
              height: '100%',
              overflow: 'hidden',
            }}
          >
            <Stage
              ref={stageRef}
              width={viewportW}
              height={viewportH}
              draggable
              dragBoundFunc={dragBound}
              onWheel={handleWheel}
              onClick={handleStageClick}
              onTap={handleStageClick}
            >
              {/* ...existing layers unchanged... */}
            </Stage>
            <LayerTogglePanel />
            <FitToViewButton onFit={fitToView} />
          </div>
        </ProjectionProvider>
      )
    }
    ```

    **CRITICAL: containerRef MUST be assigned to the same div across all render paths (loading / error / full) — otherwise the observer attaches to a node that unmounts. The loading-state div must carry `ref={containerRef}` so the observer can already measure the parent flex container while data loads.**

    **Edit 2 — `frontend/src/pages/ProjectDetail.tsx:131`**: swap hardcoded 600px for viewport-relative height. The pre-canvas block measures ~170-200px (Box p="6" + Flex header mb="4" + progress Card mb="4"). Use:

    ```tsx
    {isGenerated && (
      <Flex
        mb="4"
        style={{
          /* Measured: lines 105-127 pre-canvas block is ~170-200px tall.
             calc(100vh - 220px) leaves a 20-50px margin; minHeight guards
             short viewports. Tune here if the canvas feels cramped. */
          height: 'calc(100vh - 220px)',
          minHeight: '500px',
          borderRadius: 8,
          overflow: 'hidden',
        }}
      >
        <Box
          className="canvas-region"
          style={{ flex: 1, background: '#1a1a2e', overflow: 'hidden', position: 'relative' }}
        >
          <CanvasViewer projectId={project.id} />
        </Box>
        {/* inspector sidebar Box — UNCHANGED by this task; Task 5 will wrap it in ErrorBoundary */}
        <Box
          className="inspector-sidebar"
          style={{ width: 340, borderLeft: '1px solid var(--gray-4)', padding: 16, overflowY: 'auto' }}
        >
          <InspectorSidebarWrapper projectId={project.id} project={project} />
        </Box>
      </Flex>
    )}
    ```

    **Edit 3 — CREATE `frontend/src/components/canvas/__tests__/CanvasViewer.resize.test.tsx`** with a capturing ResizeObserver fake:

    ```tsx
    import { describe, it, expect, vi, beforeEach } from 'vitest'
    import { render } from '@testing-library/react'
    import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
    import { CanvasViewer } from '../CanvasViewer'

    // Capture the ResizeObserver callback so the test can trigger it synchronously.
    let roCallback: ResizeObserverCallback | null = null
    let roObservedEl: Element | null = null
    class CapturingRO {
      constructor(cb: ResizeObserverCallback) { roCallback = cb }
      observe(el: Element) { roObservedEl = el }
      unobserve() {}
      disconnect() { roCallback = null; roObservedEl = null }
    }

    // Stage/Layer props capture for assertions (mirror CanvasViewer.test.tsx pattern)
    const stagePropsRef: { current: Record<string, unknown> | null } = { current: null }
    vi.mock('react-konva', () => ({
      Stage: (p: Record<string, unknown>) => { stagePropsRef.current = p; return null },
      Layer: () => null,
      Circle: () => null,
      Line: () => null,
      Rect: () => null,
      Image: () => null,
      Text: () => null,
    }))

    // Mock useCanvasArtifacts with a successful fixture + mock useUIStore.
    // Reuse the exact mock shape from CanvasViewer.test.tsx (read that file first).

    beforeEach(() => {
      ;(globalThis as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
        CapturingRO as unknown as typeof ResizeObserver
      stagePropsRef.current = null
    })

    function renderWithProviders(ui: React.ReactElement) {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
    }

    describe('CanvasViewer — ResizeObserver wiring (GAP-05)', () => {
      it('updates Stage width/height when container resizes', () => {
        renderWithProviders(<CanvasViewer projectId="p1" />)
        // Initial: fallback 800/600
        expect(stagePropsRef.current?.width).toBe(800)
        expect(stagePropsRef.current?.height).toBe(600)

        // Trigger resize
        roCallback!(
          [{ contentRect: { width: 1600, height: 900 } } as unknown as ResizeObserverEntry],
          {} as ResizeObserver,
        )

        // Stage should pick up new dims
        expect(stagePropsRef.current?.width).toBe(1600)
        expect(stagePropsRef.current?.height).toBe(900)
      })

      it('recomputes minScale after resize (fitToView re-runs)', () => {
        // Use a known mapW/mapH via mock metaQ; after resize, the stage.scale call
        // should reflect the new fit scale. Assert via stagePropsRef.current or by
        // spying on computeFitToView (import star + vi.spyOn) — planner choice.
      })

      it('ignores 0×0 transient measurements without crashing', () => {
        renderWithProviders(<CanvasViewer projectId="p1" />)
        roCallback!(
          [{ contentRect: { width: 0, height: 0 } } as unknown as ResizeObserverEntry],
          {} as ResizeObserver,
        )
        // Stage stays at fallback 800×600 (no regression)
        expect(stagePropsRef.current?.width).toBe(800)
      })
    })
    ```

    The exact mock plumbing (TanStack QueryClient, useCanvasArtifacts fixture, useUIStore stub) MUST mirror what `CanvasViewer.test.tsx` already does — copy-adapt from lines 1-120 of that existing file.

    **Avoid:**
    - DO NOT observe the `containerRef` div while also setting its `width`/`height` from `viewportW/H` state — this is the feedback loop the advisor warned about. Div keeps `width:'100%', height:'100%'`; the flex parent in ProjectDetail drives its size.
    - DO NOT declare `useState` for viewport after the early returns — hooks MUST run unconditionally.
    - DO NOT remove the `width`/`height` props from CanvasViewerProps — other tests rely on them as fallback when mounting outside a flex parent.
    - DO NOT add viewportW/H to the pan-on-select effect's dep array — would re-trigger pan on every wheel+resize combo.
    - DO NOT touch `backend/medieval_forge/lib/map_generator.py` (D-04).
  </action>

  <verify>
    <automated>cd frontend && npx vitest run src/components/canvas/__tests__/CanvasViewer.resize.test.tsx src/components/canvas/__tests__/CanvasViewer.test.tsx src/hooks/__tests__/useZoomPan.test.ts --reporter=basic</automated>
  </verify>

  <acceptance_criteria>
    - `grep -n "new ResizeObserver" frontend/src/components/canvas/CanvasViewer.tsx` returns at least one match.
    - `grep -n "containerRef" frontend/src/components/canvas/CanvasViewer.tsx` returns at least one match.
    - `grep -n "useState<number>(width)\|useState(width)" frontend/src/components/canvas/CanvasViewer.tsx` returns at least one match (viewport is state, not a local const).
    - `grep -n "calc(100vh" frontend/src/pages/ProjectDetail.tsx` returns at least one match.
    - `grep -n "minHeight" frontend/src/pages/ProjectDetail.tsx` returns at least one match.
    - `grep -n "height: '600px'" frontend/src/pages/ProjectDetail.tsx` returns ZERO matches.
    - The `width: '100%'` style appears on the CanvasViewer wrapping div (not `width: viewportW`).
    - `cd frontend && npx vitest run` passes the existing 86 tests + the 3 new resize tests (≥89 total).
    - `cd frontend && npx tsc -b` exits 0.
  </acceptance_criteria>

  <done>
    CanvasViewer's Stage dimensions track the parent container via ResizeObserver; viewportW/H are useState; fitToView re-runs on resize so minScale stays correct. ProjectDetail's canvas region is viewport-relative (calc(100vh - 220px) with minHeight 500px). New resize test file green. No regressions in existing 86 vitest tests.
  </done>
</task>


<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: DIAGNOSE the condado_colors #666666 fallback against the real Iberia pipeline (GAP-04 step 1 of 2)</name>
  <files>.planning/phases/02-read-only-canvas-viewer/02-05-canvas-sizing-color-ux-fixes-PLAN.md</files>

  <read_first>
    - .planning/phases/02-read-only-canvas-viewer/02-HUMAN-UAT.md (GAP-04 section + fix_hint)
    - .planning/phases/02-read-only-canvas-viewer/02-04-e2e-pipeline-fix-PLAN.md (the synthetic integration test that passes — we need to explain WHY the real pipeline still fails despite this)
    - backend/medieval_forge/services/territories_geojson.py (sidecar emission logic; verify it runs in the real codepath)
    - backend/medieval_forge/services/generator.py (lines 63-76 whitelist; lines ~296-357 _run_pipeline_sync — trace the branch the real pipeline actually takes)
    - backend/medieval_forge/services/baronies_geojson.py (analogous barony sidecar logic)
    - frontend/src/hooks/useCanvasArtifacts.ts (confirm the URL is the sidecar file, not the Unity lookup)
    - frontend/src/components/canvas/TerritoryLayer.tsx (confirm the `?? '#666666'` fallback site)
  </read_first>

  <what-built>
    Nothing new yet. This task WRITES DIAGNOSIS to the plan's `<diagnosis>` block so Task 3 can pick the correct fix branch.
  </what-built>

  <how-to-verify>
    **Step 1:** Start the backend locally against a REAL generated Iberia project (not the synthetic fixture from 02-04's integration test). If no generated project exists, trigger `/api/projects/{id}/generate` via the UI and wait for `status: 'generated'`.

    **Step 2:** Run these three curl commands and capture output. Replace `{PID}` with your real project UUID:

    ```bash
    # A. Does the sidecar exist and is it populated?
    curl -s -w "\n[HTTP %{http_code}]\n" http://localhost:8000/api/projects/{PID}/preview/condado_colors.json | head -c 500

    # B. What are the first few feature ids in territories.geojson?
    curl -s http://localhost:8000/api/projects/{PID}/preview/territories.geojson \
      | python -c "import sys, json; d=json.load(sys.stdin); ids=[f['id'] for f in d['features'][:5]]; print('territory_ids[:5]:', ids)"

    # C. Key overlap between sidecar and geojson feature ids
    python -c "
    import json, urllib.request
    PID = '{PID}'
    cc = json.load(urllib.request.urlopen(f'http://localhost:8000/api/projects/{PID}/preview/condado_colors.json'))
    tg = json.load(urllib.request.urlopen(f'http://localhost:8000/api/projects/{PID}/preview/territories.geojson'))
    geo_ids = {f['id'] for f in tg['features']}
    print('condado_colors keys count:', len(cc))
    print('condado_colors sample keys:', list(cc.keys())[:3])
    print('territories feature ids count:', len(geo_ids))
    print('territories feature ids sample:', list(geo_ids)[:3])
    print('OVERLAP count:', len(set(cc.keys()) & geo_ids))
    print('OVERLAP pct:', round(100 * len(set(cc.keys()) & geo_ids) / max(len(geo_ids), 1), 1), '%')
    "
    ```

    **Step 3:** Paste all three outputs back into this chat.

    **Step 4 — classify by evidence, then EDIT THE `<diagnosis>` BLOCK IN THIS PLAN FILE** with which hypothesis is confirmed. Add a paragraph with commands output + the verdict.

    Hypotheses:
    - **H1 — Sidecar never emitted** (command A returns 404 or empty body). Root cause: `emit_territories_from_disk` isn't being called in the real codepath, OR a guard in `_run_pipeline_sync` skips it when the file already exists from a previous partial run. → Task 3 applies **Fix A** (trace `_run_pipeline_sync` branches 296-357 and remove any existence-skip; re-run generation; re-check).
    - **H2 — Sidecar exists but route returns empty/404** (command A returns 200 `{}` or 404 despite the file on disk). Root cause: FastAPI whitelist mismatch or path-resolution defect. → Task 3 applies **Fix B** (fix the whitelist / preview route at `api/generate.py` or equivalent).
    - **H3 — Key shape mismatch** (command A and B both populate but command C shows OVERLAP pct < 90%). Root cause: sidecar emits `{condados[i][0]: hex}` but territories.geojson emits differently-shaped ids (e.g. `condados[i].id` vs numeric index vs `C_{i:03d}`). → Task 3 applies **Fix C** (align the key emission in `territories_geojson.py` so both files use the same id).
    - **H4 — All data correct, but frontend stale** (commands A+B+C all look correct, 100% overlap). Root cause: TanStack Query cache holding a pre-02-04 empty response; user never hard-reloaded. → Task 3 applies **Fix D** (documentation-only: add a frontend cache-bust query param + regenerate `invalidateQueries` on project status change).

    **Step 5:** Reply "diagnosis committed" once the `<diagnosis>` block in `02-05-canvas-sizing-color-ux-fixes-PLAN.md` is updated with your findings + hypothesis verdict. Task 3 will then execute.
  </how-to-verify>

  <action>
    See `<how-to-verify>` above for the diagnostic steps. This task is a checkpoint — the executor runs the three curl/python commands (Steps 1-3), classifies the evidence against H1/H2/H3/H4 (Step 4), updates the `<diagnosis>` block in this plan file with the findings + confirmed hypothesis (Step 4), commits, and signals Step 5. No production code changes in this task.
  </action>

  <verify>
    <automated>grep -q "^TBD" .planning/phases/02-read-only-canvas-viewer/02-05-canvas-sizing-color-ux-fixes-PLAN.md &amp;&amp; { echo "BLOCKING: diagnosis block still TBD — Task 2 not complete"; exit 1; } || echo "diagnosis committed"</automated>
  </verify>

  <resume-signal>Type "diagnosis committed" with the hypothesis (H1/H2/H3/H4) you identified. Or describe a new hypothesis if the evidence doesn't match any of the four (e.g. "H5 — found new root cause: {describe}").</resume-signal>

  <acceptance_criteria>
    - The `<diagnosis>` block in `02-05-canvas-sizing-color-ux-fixes-PLAN.md` is no longer "TBD" — it contains: (1) command A output, (2) command B output, (3) command C output, (4) one hypothesis marked as confirmed (or a new one described).
    - Commit message references GAP-04 diagnosis: `docs(02-05): GAP-04 diagnosis — {H1|H2|H3|H4}`.
  </acceptance_criteria>

  <done>
    Diagnosis complete and committed. Task 3's executor has an unambiguous branch to execute.
  </done>
</task>


<task type="auto">
  <name>Task 3: Apply GAP-04 fix — branch based on Task 2 diagnosis</name>
  <files>backend/medieval_forge/services/territories_geojson.py, backend/medieval_forge/services/baronies_geojson.py, backend/medieval_forge/services/generator.py, backend/tests/test_territories_geojson.py, backend/tests/test_generator_e2e.py, frontend/src/hooks/useCanvasArtifacts.ts, frontend/src/pages/ProjectDetail.tsx (only files touched by the matching H1/H2/H3/H4 branch — see action)</files>

  <read_first>
    - The `<diagnosis>` block in THIS plan file (must read AFTER Task 2 has populated it — otherwise STOP).
    - backend/medieval_forge/services/territories_geojson.py (the sidecar emission logic; may need a key-alignment edit for H3)
    - backend/medieval_forge/services/baronies_geojson.py (apply analogous fix if baronies share the same defect)
    - backend/medieval_forge/services/generator.py (the `_run_pipeline_sync` branches + whitelist, for H1/H2)
    - backend/tests/test_territories_geojson.py (the pattern for adding a regression test)
    - backend/tests/test_generator_e2e.py (plan 02-04's integration test — may need EXTENSION with the real-pipeline scenario that currently passes synthetically but fails in prod)
    - frontend/src/hooks/useCanvasArtifacts.ts (for H4 cache-bust)
  </read_first>

  <action>
    **PRE-FLIGHT:** Confirm the `<diagnosis>` block in this plan file is populated. If still "TBD", HALT and return to Task 2.

    **Execute the branch matching the confirmed hypothesis. DO NOT execute multiple branches.**

    ### Branch H1 — Sidecar never emitted

    Locate the code path in `backend/medieval_forge/services/generator.py` `_run_pipeline_sync` (lines ~296-357) where `emit_territories_from_disk` is called. Per 02-04, the bare call at ~:355-356 exists. Diagnose why it doesn't fire against the real Iberia pipeline:

    - Check if there's a "skip if output exists" guard earlier in the function that bypasses the emitter when a prior partial run left residual files.
    - Check the `generated_dir` argument — if the real pipeline writes to a different dir than the one passed to `emit_*_from_disk`, the sidecar lands outside the whitelisted preview path.

    Fix:
    ```python
    # In generator.py, AFTER map_generator.generate_maps returns and BEFORE _run_pipeline_sync exits,
    # force the emitter to run unconditionally. NO existence checks.
    # (Add this only if the trace shows an existence-skip guard was the culprit.)
    emit_territories_from_disk(project_id, generated_dir, cfg_shim)
    emit_baronies_from_disk(project_id, generated_dir, cfg_shim)
    ```

    Add a backend regression test in `backend/tests/test_generator_e2e.py`:
    ```python
    def test_sidecar_reemitted_on_rerun(fake_generated_dir, monkeypatch):
        """GAP-04 H1: even when condado_colors.json already exists from a prior
        run, _run_pipeline_sync MUST overwrite it with fresh content."""
        pid, gen = fake_generated_dir
        # Pre-seed a stale sidecar with wrong keys
        (gen / "condado_colors.json").write_text(json.dumps({"STALE_KEY": "#000000"}))
        # Run pipeline
        from medieval_forge.services import generator as gen_mod
        # ...invoke _run_pipeline_sync as in the existing test...
        # Assert sidecar now has non-STALE keys
        cc = json.loads((gen / "condado_colors.json").read_text())
        assert "STALE_KEY" not in cc
        assert len(cc) >= 2  # matches fixture
    ```

    ### Branch H2 — Route returns empty/404

    Fix the whitelist in `backend/medieval_forge/services/generator.py:63-76` (verify both `condado_colors.json` and `barony_colors.json` are present — they should be post-02-04; if absent, add them). Also inspect the route in `backend/medieval_forge/api/` (find the `/preview/{filename}` route via grep) to confirm it honors the whitelist:

    ```bash
    grep -rn "preview/{filename}\|GENERATED_FILE_WHITELIST" backend/medieval_forge/api/ backend/medieval_forge/services/
    ```

    If the whitelist is right and the file exists on disk but the route returns 404, the path-resolution is broken — fix the route to use `paths.project_dir(project_id) / "generated" / filename` and reject traversal.

    Add regression test:
    ```python
    def test_preview_route_serves_sidecar(client, fake_generated_dir):
        """GAP-04 H2: /preview/condado_colors.json returns 200 + non-empty JSON."""
        pid, gen = fake_generated_dir
        # Ensure sidecar exists on disk
        (gen / "condado_colors.json").write_text(json.dumps({"C_A": "#ff0000"}))
        r = client.get(f"/api/projects/{pid}/preview/condado_colors.json")
        assert r.status_code == 200
        assert r.json() == {"C_A": "#ff0000"}
    ```

    ### Branch H3 — Key shape mismatch (MOST LIKELY per advisor hypothesis ranking)

    The 02-04 adapter writes:
    ```python
    sidecar[condados[idx][0]] = f"#{r:02x}{g:02x}{b:02x}"
    ```
    where `condados[idx][0]` is the condado id. Check what `build_territories_geojson` emits as feature id (grep for `"id":` in `territories_geojson.py`). If feature id is the numeric raster index (e.g. `0, 1, 2`) but sidecar key is the symbolic id (`C_ALPHA`), the join fails.

    Fix the MISMATCHED side — prefer changing the adapter to use the same key that `build_territories_geojson` writes. For example if the geojson emits `properties.id = condados[idx][0]` but `feature.id = idx`, align the sidecar to use `idx`:

    ```python
    # In territories_geojson.py emit_territories_from_disk — only if trace confirms H3:
    sidecar[str(idx)] = f"#{r:02x}{g:02x}{b:02x}"   # if feature.id is the numeric index
    # OR — preferred — fix build_territories_geojson so feature.id = condados[idx][0]
    # to match the sidecar. Choose whichever has fewer downstream consumers.
    ```

    Apply the identical change to `baronies_geojson.py` if barony colors exhibit the same bug.

    Add regression test in `backend/tests/test_territories_geojson.py`:
    ```python
    def test_sidecar_keys_match_territories_geojson_feature_ids(tmp_path):
        """GAP-04 H3: every key in condado_colors.json MUST be a feature id
        in territories.geojson. Zero orphans."""
        # build fixture + call emit_territories_from_disk
        # ...
        cc = json.loads((gen / "condado_colors.json").read_text())
        tg = json.loads((gen / "territories.geojson").read_text())
        geo_ids = {f["id"] for f in tg["features"]}
        assert set(cc.keys()) == geo_ids, (
            f"GAP-04 H3: sidecar keys vs feature ids mismatch. "
            f"orphaned_in_sidecar={set(cc.keys()) - geo_ids}, "
            f"missing_in_sidecar={geo_ids - set(cc.keys())}"
        )
    ```

    ### Branch H4 — Stale TanStack Query cache

    Add a cache-bust to `useCanvasArtifacts.ts` so the sidecar URL includes the project's `updated_at` (or a mount-time counter):

    ```ts
    // In useCanvasArtifacts.ts, where condado_colors.json is fetched:
    queryKey: ['canvas', projectId, 'condado-colors', project.updated_at ?? 0],
    // This invalidates cache whenever the backend updates the project.
    ```

    Also in `frontend/src/pages/ProjectDetail.tsx`, after the existing `previewTs` cache-bust effect at lines ~74-81, add:
    ```tsx
    useEffect(() => {
      if (project?.status === 'generated') {
        qc.invalidateQueries({ queryKey: ['canvas', project.id] })
      }
    }, [project?.status, project?.id, qc])
    ```

    Regression: extend an existing CanvasViewer test to assert query key includes `updated_at` so a stale cache gets busted.

    **AFTER any branch:** re-run the UAT Test 1 manually against the same real project:
    ```bash
    # Reload the browser with a hard refresh (Ctrl+Shift+R)
    # Open DevTools Network tab, confirm condado_colors.json returns non-empty with matching keys
    # Open DevTools React devtools, confirm TerritoryLayer's condadoColors prop is non-empty
    # Visually confirm no condado renders #666666
    ```

    **Avoid:**
    - DO NOT execute multiple branches — pick one based on diagnosis. If more than one hypothesis is confirmed, split into separate plans.
    - DO NOT modify `backend/medieval_forge/lib/map_generator.py` under any branch (D-04). The sidecar is written by the service-layer adapter — fixes go there.
    - DO NOT widen the whitelist beyond the two sidecar filenames even if H2 tempts you (e.g. don't add a glob).
    - DO NOT remove the `?? '#666666'` fallback in `TerritoryLayer.tsx` — it's the last-line diagnostic that told us this gap exists.
  </action>

  <verify>
    <automated>cd backend && python -m pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py tests/test_generator_e2e.py -v</automated>
  </verify>

  <acceptance_criteria>
    - The `<diagnosis>` block is populated (proves Task 2 ran).
    - Exactly ONE of H1/H2/H3/H4 fix patches is present in the commit diff (grep for the branch-specific marker: H1 → new `test_sidecar_reemitted_on_rerun`; H2 → new `test_preview_route_serves_sidecar`; H3 → new `test_sidecar_keys_match_territories_geojson_feature_ids`; H4 → new `invalidateQueries({ queryKey: ['canvas', project.id]` site in ProjectDetail.tsx).
    - `cd backend && python -m pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py tests/test_generator_e2e.py -v` passes ≥17 tests (existing 16 + at least 1 new regression).
    - `cd frontend && npx vitest run` still passes ≥89 tests (no regression — Task 1 added 3 new).
    - `git diff backend/medieval_forge/lib/map_generator.py` is empty (D-04 preserved).
    - Manual re-run of UAT Test 1 on the real Iberia project: condado fills match `condado_colors.json` hex values, zero `#666666` polygons visible with Borders OFF. (Executor notes the human verification result in the commit body.)
  </acceptance_criteria>

  <done>
    GAP-04 root cause identified and fixed; regression test added proving the specific hypothesis; manual re-run of UAT Test 1 against a real Iberia project shows real condado fills end-to-end.
  </done>
</task>


<task type="auto">
  <name>Task 4: Lower label zoom threshold to 1.5× + add Radix Tooltip to Labels checkbox (GAP-08)</name>
  <files>frontend/src/components/canvas/DecorationsLayer.tsx, frontend/src/components/canvas/LayerTogglePanel.tsx, frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx</files>

  <read_first>
    - frontend/src/components/canvas/DecorationsLayer.tsx (lines 13, 78-80)
    - frontend/src/components/canvas/LayerTogglePanel.tsx (ENTIRE file — 35 lines)
    - frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx (lines 107-108 MUST be updated to assert 1.5)
    - frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx (verify existing 5 tests still pass after Tooltip wrapping)
    - `@radix-ui/themes` Tooltip component API (check `node_modules/@radix-ui/themes` or the CLAUDE.md Radix note — Tooltip takes `content` prop and wraps its trigger child)
  </read_first>

  <action>
    **Edit 1 — `frontend/src/components/canvas/DecorationsLayer.tsx:13`**: lower the threshold.

    ```tsx
    /**
     * Label gate: labels render only when the stage is zoomed in to at least
     * 1.5× the fit-to-view scale. UAT feedback (GAP-08) showed 2.0× was too high
     * — users perceived the Labels toggle as broken at default zoom. Compromise
     * value per 02-HUMAN-UAT.md fix_hint.
     */
    export const LABEL_ZOOM_THRESHOLD_RELATIVE = 1.5
    ```

    **Edit 2 — `frontend/src/components/canvas/LayerTogglePanel.tsx`**: wrap the Labels row in a Radix Tooltip. Replace the `.map` body with an explicit conditional:

    ```tsx
    import { Card, Flex, Text, Checkbox, Tooltip } from '@radix-ui/themes'
    import { useUIStore, type LayerName } from '../../stores/uiStore'

    const LAYERS: { key: LayerName; label: string; hint?: string }[] = [
      { key: 'terrain', label: 'Terrain' },
      { key: 'territories', label: 'Territories' },
      { key: 'borders', label: 'Borders' },
      { key: 'capitals', label: 'Capitals' },
      { key: 'labels', label: 'Labels', hint: 'Zoom in 1.5× to show labels' },
    ]

    export function LayerTogglePanel() {
      const layerVisibility = useUIStore((s) => s.layerVisibility)
      const toggleLayer = useUIStore((s) => s.toggleLayer)

      return (
        <Card
          variant="surface"
          style={{ position: 'absolute', top: 12, left: 12, zIndex: 10, width: 160 }}
        >
          <Flex direction="column" gap="2">
            <Text size="2" weight="bold">Layers</Text>
            {LAYERS.map(({ key, label, hint }) => {
              const row = (
                <Flex key={key} align="center" gap="2">
                  <Checkbox
                    checked={layerVisibility[key]}
                    onCheckedChange={() => toggleLayer(key)}
                  />
                  <Text size="2">{label}</Text>
                </Flex>
              )
              return hint ? (
                <Tooltip key={key} content={hint}>
                  {row}
                </Tooltip>
              ) : (
                row
              )
            })}
          </Flex>
        </Card>
      )
    }
    ```

    **Edit 3 — `frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx`**: flip the threshold assertion at lines 107-108:

    ```tsx
    it('exposes LABEL_ZOOM_THRESHOLD_RELATIVE = 1.5', () => {
      expect(LABEL_ZOOM_THRESHOLD_RELATIVE).toBe(1.5)
    })
    ```

    Also audit the other gating tests in that file (lines 184-233 region) — they use expressions like `currentScale = 2.0 * minScale`, `currentScale = 1.9 * minScale` to straddle the threshold. After the threshold drop to 1.5, those tests may need their straddling values recomputed:
    - Tests that previously asserted "NO labels at 1.5× minScale" MUST now assert "labels DO render at 1.5× minScale".
    - Tests using `1.9 * minScale` or `2.0 * minScale` still work (both ≥1.5) and don't need changes.
    - Tests using `0.5 * minScale` or `1.0 * minScale` still work (both <1.5) and don't need changes.
    - ONLY adjust tests in the 1.5–1.9 range. Read each assertion carefully.

    **Avoid:**
    - DO NOT import Tooltip from `@radix-ui/react-tooltip` (that's the primitive — use the themed wrapper from `@radix-ui/themes`).
    - DO NOT reach into the DecorationsLayer gating constant with a different name — `LABEL_ZOOM_THRESHOLD_RELATIVE` is imported by tests; keep the name.
    - DO NOT add animation or delay props to the Tooltip — Radix defaults are fine.
    - DO NOT change the 2.0 to 1.5 in `DecorationsLayer.tsx` comment if you kept the old comment — update the JSDoc to match.
  </action>

  <verify>
    <automated>cd frontend && npx vitest run src/components/canvas/__tests__/DecorationsLayer.test.tsx src/components/canvas/__tests__/LayerTogglePanel.test.tsx --reporter=basic</automated>
  </verify>

  <acceptance_criteria>
    - `grep -n "LABEL_ZOOM_THRESHOLD_RELATIVE = 1.5" frontend/src/components/canvas/DecorationsLayer.tsx` returns exactly 1 match.
    - `grep -n "LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0" frontend/src/components/canvas/DecorationsLayer.tsx` returns 0 matches.
    - `grep -n "Tooltip" frontend/src/components/canvas/LayerTogglePanel.tsx` returns ≥1 match.
    - `grep -n "Zoom in 1.5" frontend/src/components/canvas/LayerTogglePanel.tsx` returns 1 match.
    - `grep -n "toBe(1.5)" frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx` returns 1 match.
    - `grep -n "toBe(2.0)" frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx` returns 0 matches.
    - DecorationsLayer tests pass: `cd frontend && npx vitest run src/components/canvas/__tests__/DecorationsLayer.test.tsx --reporter=basic` is green.
    - LayerTogglePanel tests pass: `cd frontend && npx vitest run src/components/canvas/__tests__/LayerTogglePanel.test.tsx --reporter=basic` is green (5/5 or higher — Tooltip wrapping MUST NOT break checkbox state queries).
    - `cd frontend && npx tsc -b` exits 0.
  </acceptance_criteria>

  <done>
    Threshold lowered to 1.5 in code + test; Labels checkbox wrapped in a Radix Tooltip that reads "Zoom in 1.5× to show labels"; all existing tests pass.
  </done>
</task>


<task type="auto">
  <name>Task 5: Wrap InspectorSidebarWrapper in ErrorBoundary with visible fallback (GAP-07)</name>
  <files>frontend/src/pages/ProjectDetail.tsx, frontend/src/pages/__tests__/ProjectDetail.errorBoundary.test.tsx, frontend/package.json, frontend/package-lock.json</files>

  <read_first>
    - frontend/src/pages/ProjectDetail.tsx (lines 138-145 — Inspector sidebar mount; lines 1-11 — existing Radix imports; line 103 onwards — consider where to place the ErrorBoundary)
    - frontend/package.json (confirm react-error-boundary absent — `grep react-error-boundary` returns 0)
    - frontend/src/components/canvas/InspectorSidebar.tsx (existing component — no changes; we wrap the WRAPPER, not this)
    - frontend/src/test-setup.ts (ResizeObserver stub already handles nested Radix Tooltip/Callout)
  </read_first>

  <action>
    **Edit 1 — install dependency. Run this command AT THE REPOSITORY ROOT:**
    ```bash
    cd frontend && npm install react-error-boundary@^4
    ```

    Note: version ^4 supports React 19 (project's React 18 constraint is noted as CAUTION in CLAUDE.md; React 19 was chosen at init — confirm `react: ^19.2.0` in package.json before installing). If npm reports peer-dep warning for React 19, `react-error-boundary` still resolves correctly — do NOT pass `--legacy-peer-deps`.

    Confirm:
    ```bash
    grep -n "react-error-boundary" frontend/package.json
    ```
    Should show the new dep under `"dependencies"`.

    **Edit 2 — `frontend/src/pages/ProjectDetail.tsx`**: add import + wrap the InspectorSidebarWrapper at line 142.

    Add to imports (line 3 area):
    ```tsx
    import { ErrorBoundary } from 'react-error-boundary'
    ```

    Update the inspector sidebar Box (lines 138-144) to wrap the inner call in ErrorBoundary:
    ```tsx
    <Box
      className="inspector-sidebar"
      style={{ width: 340, borderLeft: '1px solid var(--gray-4)', padding: 16, overflowY: 'auto' }}
    >
      <ErrorBoundary
        onError={(err) => {
          // Log full stack to console for developer triage — DO NOT render the
          // stack into the fallback UI (security: avoid leaking internals to the
          // end user per threat model T-02-05-02).
          // eslint-disable-next-line no-console
          console.error('[InspectorSidebar] boundary caught:', err)
        }}
        fallback={
          <Callout.Root color="red" size="1">
            <Callout.Text>
              Sidebar failed to load — check console.
            </Callout.Text>
          </Callout.Root>
        }
      >
        <InspectorSidebarWrapper projectId={project.id} project={project} />
      </ErrorBoundary>
    </Box>
    ```

    Note: `Callout` is already imported from `@radix-ui/themes` in ProjectDetail.tsx:3 — no new import needed.

    **Edit 3 — CREATE `frontend/src/pages/__tests__/ProjectDetail.errorBoundary.test.tsx`**:

    ```tsx
    import { describe, it, expect, vi } from 'vitest'
    import { render, screen } from '@testing-library/react'
    import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
    import { MemoryRouter, Route, Routes } from 'react-router-dom'
    import { Theme } from '@radix-ui/themes'
    import { ProjectDetail } from '../ProjectDetail'

    // Mock useCanvasArtifacts to throw — simulates the silent-failure scenario.
    vi.mock('../../hooks/useCanvasArtifacts', () => ({
      useCanvasArtifacts: () => {
        throw new Error('Simulated artifact failure — GAP-07 test')
      },
    }))

    // Minimal useProject mock so isGenerated=true and the canvas region renders.
    vi.mock('../../api/client', async (orig) => {
      const actual = await (orig as () => Promise<Record<string, unknown>>)()
      return {
        ...actual,
        useProject: () => ({
          data: {
            id: 'test-pid',
            name: 'Test project',
            status: 'generated',
            country_qid: 'Q29',
            period_start: 800,
            period_end: 900,
          },
          isLoading: false,
          error: null,
        }),
        useUpdateProject: () => ({ mutateAsync: vi.fn(), isPending: false }),
        useIngestStream: () => ({ isStreaming: false, lines: [], error: null, start: vi.fn() }),
        useGenerate: () => ({ mutate: vi.fn(), isPending: false, error: null }),
        useExport: () => ({ mutate: vi.fn(), isPending: false, error: null }),
        useIngestStatus: () => ({ data: null }),
        useTerritoryTemplate: () => ({ data: null }),
        useRenderModern: () => ({ mutate: vi.fn(), isPending: false, error: null }),
      }
    })

    describe('ProjectDetail — InspectorSidebar ErrorBoundary (GAP-07)', () => {
      it('renders fallback when InspectorSidebarWrapper throws', () => {
        // Suppress expected error output in test logs
        const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

        const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
        render(
          <QueryClientProvider client={qc}>
            <Theme>
              <MemoryRouter initialEntries={['/projects/test-pid']}>
                <Routes>
                  <Route path="/projects/:id" element={<ProjectDetail />} />
                </Routes>
              </MemoryRouter>
            </Theme>
          </QueryClientProvider>,
        )

        expect(screen.getByText(/Sidebar failed to load/i)).toBeInTheDocument()

        errSpy.mockRestore()
      })
    })
    ```

    **Avoid:**
    - DO NOT render `err.stack` or `err.message` into the fallback UI — users see a generic message; full error goes to `console.error` only (threat model T-02-05-02 information-disclosure mitigation).
    - DO NOT wrap `CanvasViewer` in the same boundary — CanvasViewer has its own loading/error branches and we don't want to mask Konva init errors with a generic message. Boundary is ONLY around `InspectorSidebarWrapper`.
    - DO NOT use `--legacy-peer-deps` when installing `react-error-boundary`.
    - DO NOT remove the empty-data branch `if (!metaQ.data || !territoriesQ.data) { return <Text>No inspector data.</Text> }` inside InspectorSidebarWrapper — ErrorBoundary catches throws, NOT happy-path empty states; both handlers must coexist.
  </action>

  <verify>
    <automated>cd frontend && npx vitest run src/pages/__tests__/ProjectDetail.errorBoundary.test.tsx --reporter=basic</automated>
  </verify>

  <acceptance_criteria>
    - `grep -n "react-error-boundary" frontend/package.json` returns ≥1 match (dependency present).
    - `grep -n "ErrorBoundary" frontend/src/pages/ProjectDetail.tsx` returns ≥2 matches (import + usage).
    - `grep -n "Sidebar failed to load" frontend/src/pages/ProjectDetail.tsx` returns 1 match.
    - `cd frontend && npx vitest run src/pages/__tests__/ProjectDetail.errorBoundary.test.tsx --reporter=basic` passes 1 test.
    - Full suite: `cd frontend && npx vitest run` passes ≥90 tests (89 from Task 1 + 1 from Task 5).
    - `cd frontend && npx tsc -b` exits 0.
    - No `err.stack` or `err.message` appears in the Callout.Root fallback JSX (grep for `err\.message` in ProjectDetail.tsx returns 0 matches inside the ErrorBoundary fallback).
  </acceptance_criteria>

  <done>
    InspectorSidebarWrapper now has a visible ErrorBoundary fallback; throw-scenario test green; full error goes to console.error only (no stack leak in UI).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → DOM (ResizeObserver) | ResizeObserver fires from the browser's layout engine. Observed entries are trusted (browser-generated). Callbacks invoked synchronously during layout — uncontrolled frequency is the risk. |
| local backend ↔ local frontend (GAP-04 diagnostic curl) | Diagnostic curl runs against `http://localhost:8000` — no external surface. |
| ErrorBoundary caught error → fallback UI | Errors thrown by `InspectorSidebarWrapper` (e.g. TanStack Query network failures, parse errors) could leak internal paths / SQL queries / stack traces if surfaced to the user. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-05-01 | Denial of Service | `CanvasViewer` ResizeObserver callback | mitigate | Guard against 0×0 transient measurements in the observer callback (explicit `if (cr.width > 0 && cr.height > 0)` check — see Task 1 action block). Observed element is a single `<div>`; no child-list mutations, no nested observers. React's setState is batched so rapid resize events collapse into one render per frame. No debounce/rAF needed at typical viewport-resize cadence (≤100 events/sec per browser spec). If profiling post-landing shows >16ms callback time, add a `requestAnimationFrame` wrapper as follow-up. |
| T-02-05-02 | Information Disclosure | `ErrorBoundary` fallback in `ProjectDetail.tsx` | mitigate | Fallback renders a GENERIC message `"Sidebar failed to load — check console."` — no `err.message`, no `err.stack`, no path fragments. Full error goes to `console.error` via the `onError` prop for developer triage. Explicit grep check in acceptance criteria (Task 5) prevents regression that would paste err details into the Callout body. |
| T-02-05-03 | Tampering | `condado_colors.json` sidecar served by backend `/preview/{filename}` | accept | File is produced by the local backend inside `~/.medieval-forge/projects/{uuid}/generated/` and served via the whitelisted `/preview/{filename}` route. No external writer; no network input. Already covered by T-02-04-01 in plan 02-04. |
| T-02-05-04 | Information Disclosure | GAP-04 diagnostic curl commands capture project UUID + territory ids | accept | Diagnostic runs on localhost only. Output pasted by the developer into the plan's `<diagnosis>` block, which is committed to the local repo. If the repo is private (standard) no external exposure; if public, developer SHOULD redact the project UUID before committing — flagged in Task 2's "how-to-verify" step (developer discretion, low-risk because UUIDs are per-install and non-linkable). |
| T-02-05-05 | Denial of Service | GAP-04 diagnostic Python one-liner with `urllib.request.urlopen` | accept | Localhost-only, run manually by developer with full control over input URLs. No auto-retry, no loop. Negligible risk. |
| T-02-05-06 | Elevation of Privilege | `react-error-boundary` v4 install | accept | Vetted npm package (4M+ weekly downloads, TypeScript-first, React 19 compat per repo README). Install via standard `npm install` — no postinstall scripts known to be malicious. Matches repo's existing supply-chain posture (all frontend deps from npm registry). |
</threat_model>

<verification>
Run after all tasks complete:

1. **Frontend tests:** `cd frontend && npx vitest run` — expect ≥90/90 green (86 existing + 3 resize + 1 error-boundary; Task 3 branches may add 0-1 more depending on hypothesis).
2. **Frontend type-check:** `cd frontend && npx tsc -b` — expect exit 0.
3. **Backend tests (GAP-04 regression):** `cd backend && python -m pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py tests/test_generator_e2e.py -v` — expect ≥17 tests green (16 existing + at least 1 GAP-04 branch-specific regression).
4. **Grep sweep:**
   - `grep -n "new ResizeObserver" frontend/src/components/canvas/CanvasViewer.tsx` → ≥1.
   - `grep -n "height: '600px'" frontend/src/pages/ProjectDetail.tsx` → 0.
   - `grep -n "calc(100vh" frontend/src/pages/ProjectDetail.tsx` → ≥1.
   - `grep -n "LABEL_ZOOM_THRESHOLD_RELATIVE = 1.5" frontend/src/components/canvas/DecorationsLayer.tsx` → 1.
   - `grep -n "LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0" frontend/src/components/canvas/DecorationsLayer.tsx` → 0.
   - `grep -n "Tooltip" frontend/src/components/canvas/LayerTogglePanel.tsx` → ≥1.
   - `grep -n "ErrorBoundary" frontend/src/pages/ProjectDetail.tsx` → ≥2.
   - `grep -n "react-error-boundary" frontend/package.json` → ≥1.
5. **D-04 preservation:** `git diff backend/medieval_forge/lib/map_generator.py` → empty.

**UAT unblock map — after this plan ships, human MUST re-run 02-HUMAN-UAT.md items:**

| UAT Item | Previously | Unblocked By | Expected After |
|----------|------------|--------------|----------------|
| #1 Condado fills match | FAILED | Task 3 (GAP-04 fix applied to matching branch) | PASSED |
| #3 Drag-pan smoothness | pending (blocked by #11) | Task 1 (GAP-05) | PASSED |
| #4 Cursor-anchored wheel zoom | pending (blocked by #11) | Task 1 (GAP-05) | PASSED |
| #5 Click-select + neighbor chip pan | FAILED | Task 1 (GAP-05 resolves GAP-06 downstream) | PASSED |
| #6 Esc + empty-Stage deselect | pending (blocked by #11) | Task 1 (GAP-05) | PASSED |
| #7 Label gate at 2× minScale | FAILED (UX) | Task 4 (GAP-08: threshold 1.5 + tooltip) | PASSED (new expected: labels at ≥1.5× with tooltip hint) |
| #8 Fit-to-view button + Ctrl+0 | pending (blocked by #11) | Task 1 (GAP-05) | PASSED |
| #9 D-06.3 capital sentinel | pending (blocked by #11) | Task 1 (GAP-05) unblocks selection to test sentinel | PASSED |
| #11 Stage fills viewport (NEW) | FAILED (critical) | Task 1 (GAP-05) | PASSED |
| Defensive: sidebar throws → visible fallback | (not tested previously) | Task 5 (GAP-07) | Fallback visible on manual throw simulation (can be skipped in UAT — covered by vitest) |

Human tester should update 02-HUMAN-UAT.md `status` fields after re-run; then run `/gsd-verify-phase 02` to regenerate VERIFICATION.md.
</verification>

<success_criteria>
- GAP-05 (keystone): CanvasViewer Stage fills the entire canvas-region Box; resizing the browser viewport re-runs fitToView so minScale tracks the new Stage dimensions. ProjectDetail canvas region uses `calc(100vh - 220px)` with `minHeight: 500px`.
- GAP-06 (downstream): after GAP-05 ships, clicking any visible condado selects it with gold 3px outline + InspectorSidebar shows all 4 property groups. Human UAT re-run confirms no "blank" regression.
- GAP-04: diagnosis committed to the `<diagnosis>` block; the matching fix branch (H1/H2/H3/H4) landed with a regression test proving the specific root cause; real Iberia project renders real condado colors (no `#666666`).
- GAP-07: InspectorSidebarWrapper wrapped in ErrorBoundary; throw-scenario vitest asserts fallback text visible; console.error receives full error (information-disclosure mitigation).
- GAP-08: `LABEL_ZOOM_THRESHOLD_RELATIVE = 1.5`; Radix Tooltip on Labels checkbox reads "Zoom in 1.5× to show labels"; DecorationsLayer test asserts the new threshold.
- D-04 preserved: `git diff backend/medieval_forge/lib/map_generator.py` is empty.
- Zero regressions: existing 86 vitest tests + 16 backend tests (from 02-04) still pass.
- The 9 previously-FAILED/BLOCKED UAT items in 02-HUMAN-UAT.md become re-runnable and are expected to PASS on human re-test.
</success_criteria>

<output>
After completion, create `.planning/phases/02-read-only-canvas-viewer/02-05-SUMMARY.md` describing:
- GAP-05 fix: ResizeObserver wiring in CanvasViewer + viewport-relative canvas region in ProjectDetail (with exact line numbers + the final `calc(...)` value landed)
- GAP-06: verified as downstream symptom of GAP-05 — no separate fix applied; human UAT confirmation result
- GAP-04 fix: diagnosis hypothesis confirmed + which branch of Task 3 executed + regression test added
- GAP-07 fix: react-error-boundary v{X} installed + ErrorBoundary wrapping pattern + throw-scenario test
- GAP-08 fix: threshold lowered to 1.5 + Radix Tooltip on Labels row + DecorationsLayer test updated
- UAT items still pending human re-run (from the Verification table)
- Threat-model mitigations that landed (T-02-05-01 viewport guard; T-02-05-02 generic fallback message)
</output>
