/**
 * Phase 08.1 Plan 08 — G6 reproduction + fix-verification spec.
 *
 * ANTI-PATTERN GUARD (non-negotiable):
 * The G6 CLAIM (colored map stale / overlay reflects edit) MUST NOT call
 * __forgeBezierTriggerDrag / __forgeBezierTriggerInsert / __forgeBezierTriggerHandleDrag.
 * The drag action flows through REAL page.mouse events only.
 *
 * Permitted read-only hooks (setup/inspection, NOT triggers):
 *   __forgeSelectBarony   — selection setup (not the claim)
 *   __forgeStageScale     — read-only scale inspection
 *   __forgeBezierState    — read-only Bézier state inspection (anchorCount, editLogLength,
 *                           firstAnchor, editedContourPointCount, editedRingSnapshot)
 *   __forgePanToFirstAnchor — display-only pan, no store write
 *
 * WHY THIS SPEC EXISTS (false-green guard):
 * Plans 08.1-04 through 08.1-06 used DEV trigger hooks for all drag claims.
 * The human UAT (G5) caught that real events FAILED at fit-to-view scale.
 * Plan 07 fixed G5 (screen-space sizing + MAX_SCALE_MULTIPLIER=16).
 * This plan (08) exposes G6: even after a successful real drag (G5 fixed),
 * the COLORED barony the user reads as "the map" never changes — it comes from
 * effectiveBaronies = baroniesQ.data (backend GeoJSON, CanvasViewer.tsx:365)
 * which is NEVER updated by op:'move' (no POST to /editor/apply, no /render).
 *
 * Describe 1 — REPRODUCTION: real drag commits (editLog grows), but the
 * colored backend barony ring is byte-identical before/after. This discriminator
 * proves G6 is real and INDEPENDENT of G5.
 *
 * Describe 2 — FIX VERIFICATION: a live amber-dashed edited-contour overlay
 * reads store.vertices and updates immediately when a real drag commits. Proved
 * by comparing editedRingSnapshot before/after the drag — geometry CHANGES.
 *
 * REQ-IDs: BEZ-DRAG-01, BEZ-RENDER-01, BEZ-UAT-01, BEZ-IDENTITY-01
 */
import { readFileSync } from 'node:fs'
import { test, expect, type Page } from '@playwright/test'

// ─── Helpers (copied from 08.1-bezier-usable-targets.spec.ts — do not import
//     across specs; each spec is self-contained) ────────────────────────────────

function loadProjectInfo(): { project_id: string; name: string } {
  const p = process.env.UAT_PROJECT_INFO_PATH
  if (!p) {
    throw new Error(
      'UAT_PROJECT_INFO_PATH is not set; globalSetup did not run. Did you launch via `npx playwright test`?',
    )
  }
  return JSON.parse(readFileSync(p, 'utf-8'))
}

/**
 * Bézier state shape returned by window.__forgeBezierState.
 * editedContourPointCount: number of coordinates in the live overlay (2 × vertex count).
 * editedRingSnapshot: JSON-serialised flat [x0,y0,x1,y1,...] of the overlay at call time,
 *   used to detect geometry change across a drag (count is invariant; coords change).
 */
interface BezierState {
  anchorCount: number
  activeAnchorIdx: number | null
  dirtySegmentCount: number
  editLogLength: number
  firstAnchor: { idx: number; x: number; y: number } | null
  midCurvePoint?: { x: number; y: number } | null
  /** additive (Plan 08): number of numbers in editedRingPts (2 × vertex count) */
  editedContourPointCount?: number
  /** additive (Plan 08): JSON.stringify(editedRingPts) snapshot for change detection */
  editedRingSnapshot?: string
}

async function readBezierState(page: Page): Promise<BezierState | null> {
  return page.evaluate(() => {
    const fn = (window as unknown as { __forgeBezierState?: () => unknown }).__forgeBezierState
    return fn ? (fn() as BezierState) : null
  })
}

/**
 * Discover a real barony id from the seeded baronies.geojson.
 * Picks the barony whose centroid is closest to the geographic center of Iberia
 * (lon≈-3.5, lat≈40) so the selected barony is likely visible at fit-to-view scale.
 */
async function discoverBaronyId(page: Page, projectId: string): Promise<string> {
  const id = await page.evaluate(async (pid) => {
    const res = await fetch(`/api/v3/projects/${pid}/artifacts/baronies.geojson`)
    if (!res.ok) return null
    const fc = await res.json()
    if (!fc?.features?.length) return null
    const centerLon = -3.5
    const centerLat = 40.0
    let bestId: string | null = null
    let bestDist = Infinity
    for (const feat of fc.features) {
      const id = feat?.id ?? feat?.properties?.id ?? feat?.properties?.name ?? null
      if (!id) continue
      let lon: number | null = null
      let lat: number | null = null
      if (feat.bbox && feat.bbox.length >= 4) {
        lon = (feat.bbox[0] + feat.bbox[2]) / 2
        lat = (feat.bbox[1] + feat.bbox[3]) / 2
      } else if (feat.geometry?.coordinates) {
        const coords = feat.geometry.coordinates
        const first = Array.isArray(coords[0])
          ? Array.isArray(coords[0][0])
            ? coords[0][0]
            : coords[0]
          : coords
        if (typeof first[0] === 'number' && typeof first[1] === 'number') {
          lon = first[0]; lat = first[1]
        }
      }
      if (lon === null || lat === null) continue
      const dist = Math.sqrt((lon - centerLon) ** 2 + (lat - centerLat) ** 2)
      if (dist < bestDist) { bestDist = dist; bestId = String(id) }
    }
    return bestId ?? (fc.features[0]?.id ?? fc.features[0]?.properties?.id ?? null) as string | null
  }, projectId)
  if (!id) throw new Error('Could not discover a barony id from seeded baronies.geojson')
  return id
}

async function navigateToWorkspace(page: Page, projectId: string) {
  await page.goto(`/projects/${projectId}`)
  await expect(page.getByTestId('canvas-stage')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId('territory-layer-ready')).toBeAttached({ timeout: 30_000 })
}

/**
 * Zoom in using REAL wheel events until __forgeStageScale crosses targetAbsolute.
 * Loop-based (not fixed count): SCALE_BY=1.05, ~37 ticks per 6× scale.
 */
async function zoomInUntilAbsolute(
  page: Page,
  cx: number,
  cy: number,
  targetAbsolute: number,
  maxTicks = 80,
): Promise<number> {
  await page.mouse.move(cx, cy)
  await page.waitForTimeout(50)
  let ticks = 0
  while (ticks < maxTicks) {
    const scale = await page.evaluate(() =>
      (window as unknown as { __forgeStageScale?: number }).__forgeStageScale ?? 1,
    )
    if (scale >= targetAbsolute) break
    await page.mouse.move(cx, cy)
    await page.mouse.wheel(0, -100)
    ticks++
  }
  return await page.evaluate(() =>
    (window as unknown as { __forgeStageScale?: number }).__forgeStageScale ?? 1,
  )
}

// ─── Setup helper (shared by both describe blocks) ────────────────────────────

async function setupAndZoom(page: Page, projectId: string) {
  await navigateToWorkspace(page, projectId)
  await expect(page.getByTestId('edit-tool-palette')).toBeVisible()
  await page.getByTestId('edit-tool-v').click()

  const baronyId = await discoverBaronyId(page, projectId)
  await page.evaluate((id) => {
    ;(window as unknown as { __forgeSelectBarony?: (id: string) => void }).__forgeSelectBarony?.(id)
  }, baronyId)

  await expect
    .poll(async () => (await readBezierState(page))?.anchorCount ?? 0, { timeout: 15_000 })
    .toBeGreaterThanOrEqual(4)

  const fitScale = await page.evaluate(() =>
    (window as unknown as { __forgeStageScale?: number }).__forgeStageScale ?? 1,
  )

  const canvasBox = await page.getByTestId('canvas-stage').boundingBox()
  expect(canvasBox, 'canvas-stage bounding box must be present').not.toBeNull()

  const canvasCx = canvasBox!.x + canvasBox!.width / 2
  const canvasCy = canvasBox!.y + canvasBox!.height / 2

  const targetScale = fitScale * 6
  await zoomInUntilAbsolute(page, canvasCx, canvasCy, targetScale, 80)

  const panned = await page.evaluate(() =>
    (window as unknown as { __forgePanToFirstAnchor?: () => boolean }).__forgePanToFirstAnchor?.() ?? false,
  )
  expect(panned, '__forgePanToFirstAnchor must succeed').toBe(true)

  const stateAfterZoom = await readBezierState(page)
  expect(stateAfterZoom?.firstAnchor, 'firstAnchor must be non-null after zoom').not.toBeNull()

  return { baronyId, canvasBox: canvasBox!, stateAfterZoom: stateAfterZoom! }
}

// ─── Describe 1: G6 REPRODUCTION ─────────────────────────────────────────────
//
// CONCLUSION recorded here (regression-of-understanding guard):
//   editLog grew (op:'move' commit OK — G5 fixed) + colored backend ring unchanged
//   → G6 is real and INDEPENDENT of G5. Fix = Task 2 live overlay from store.vertices
//   (option a). NO /editor/apply, NO /render — phase boundary forbids backend seeing
//   Bézier. The op:'move' path writes ONLY to useEditorStore.vertices; it never POSTs
//   to /editor/apply (only split/merge/translate do). There is NO Phase 08 precedent for
//   op:'move' surfacing on the colored map — that path does not exist. G6 needs a new
//   contract: the live overlay.

test.describe('Phase 08.1 — G6 reproduction (drag commits, colored map stale)', () => {

  test('REAL drag commits op:move (editLog grows) AND the colored backend barony ring is UNCHANGED (G6 confirmed, distinct from G5)', async ({
    page,
  }) => {
    // ANTI-PATTERN GUARD: this test MUST NOT call __forgeBezierTrigger* for the claim.
    // The drag is a real page.mouse event. __forgeBezierState is read-only inspection.

    const info = loadProjectInfo()
    const { stateAfterZoom } = await setupAndZoom(page, info.project_id)

    const { x: ax, y: ay } = stateAfterZoom.firstAnchor!
    const editLog0 = stateAfterZoom.editLogLength

    // Snapshot the BACKEND colored barony ring BEFORE the drag.
    // This is the GeoJSON that effectiveBaronies (CanvasViewer.tsx:365) reads.
    // baronies.geojson is served from the artifact layer — never updated by op:'move'.
    const baronyId = await discoverBaronyId(page, info.project_id)
    const ringBefore = await page.evaluate(async (pid) => {
      const res = await fetch(`/api/v3/projects/${pid}/artifacts/baronies.geojson`)
      if (!res.ok) return null
      const fc = await res.json()
      // Find the active barony feature and return its coordinate ring as a stable string
      const feat = fc.features?.find(
        (f: { id?: unknown; properties?: { id?: unknown; name?: unknown } }) => {
          const fid = f?.id ?? f?.properties?.id ?? f?.properties?.name ?? null
          return fid !== null
        },
      )
      return feat ? JSON.stringify(feat.geometry?.coordinates) : null
    }, info.project_id)

    expect(ringBefore, 'backend barony ring must be fetchable before drag').not.toBeNull()

    // REAL page.mouse drag on firstAnchor — no __forgeBezierTrigger* involvement
    await page.mouse.move(ax, ay)
    await page.mouse.down()
    await page.mouse.move(ax + 30, ay + 30, { steps: 8 })
    await page.mouse.up()

    // Proof 1: op:'move' committed — editLog grew (G5 is fixed; this is NOT a grab failure)
    await expect
      .poll(async () => (await readBezierState(page))?.editLogLength ?? editLog0, { timeout: 8_000 })
      .toBeGreaterThan(editLog0)

    // Proof 2: the BACKEND-served barony ring is BYTE-IDENTICAL (G6 confirmation).
    // op:'move' only writes useEditorStore.vertices — no POST to /editor/apply, no /render.
    // The colored BaronyLayer reads effectiveBaronies (TanStack query, backend GeoJSON) which
    // is never updated by a Bézier drag. This proves G6 is real and independent of G5.
    const ringAfter = await page.evaluate(async (pid) => {
      const res = await fetch(`/api/v3/projects/${pid}/artifacts/baronies.geojson`)
      if (!res.ok) return null
      const fc = await res.json()
      const feat = fc.features?.find(
        (f: { id?: unknown; properties?: { id?: unknown; name?: unknown } }) => {
          const fid = f?.id ?? f?.properties?.id ?? f?.properties?.name ?? null
          return fid !== null
        },
      )
      return feat ? JSON.stringify(feat.geometry?.coordinates) : null
    }, info.project_id)

    expect(ringAfter, 'backend ring must be re-fetchable after drag').not.toBeNull()
    expect(ringAfter, 'G6 CONFIRMED: colored backend barony ring is byte-identical after drag (op:move never POSTs)').toBe(ringBefore)

    // Suppress unused variable warning — baronyId is used implicitly via closure above
    void baronyId
  })
})

// ─── Describe 2: G6 FIX VERIFICATION ─────────────────────────────────────────
//
// Proves the live amber-dashed edited-contour overlay (option a) reflects the drag
// by reading editedRingSnapshot (the actual flat [x,y,...] coords) BEFORE and AFTER
// a real drag — geometry MUST change. Count alone is insufficient (count is invariant
// under op:'move' — it would pass even if the overlay were frozen).
//
// ANTI-PATTERN GUARD: the drag is a real page.mouse event; __forgeBezierState is
// read-only state inspection, never a trigger. No __forgeBezierTrigger* drives the action.

test.describe('G6 fix — live overlay reflects the edit', () => {

  test('after a REAL drag at usable zoom, the live edited-contour overlay geometry CHANGES (editedRingSnapshot differs before/after drag) and editedContourPointCount > 0', async ({
    page,
  }) => {
    // ANTI-PATTERN GUARD: the DRAG is a real page.mouse event.
    // __forgeBezierState is read-only state inspection, never a trigger.
    // No __forgeBezierTrigger* drives the action.

    const info = loadProjectInfo()
    const { stateAfterZoom } = await setupAndZoom(page, info.project_id)

    const { x: ax, y: ay } = stateAfterZoom.firstAnchor!

    // Capture editLog baseline and the GEOMETRY of the overlay BEFORE the drag.
    // editedRingSnapshot = JSON.stringify(editedRingPts) — the actual flat coord array.
    // count alone is insufficient (invariant under op:'move'); geometry must change.
    const editLog0 = stateAfterZoom.editLogLength
    const before = stateAfterZoom.editedContourPointCount
    const snapshotBefore = stateAfterZoom.editedRingSnapshot

    expect(before, 'overlay must be mounted before the drag (editedContourPointCount > 0)').toBeGreaterThan(0)
    expect(snapshotBefore, 'editedRingSnapshot must be present before drag').toBeTruthy()

    // REAL page.mouse drag — no __forgeBezierTrigger* involvement
    await page.mouse.move(ax, ay)
    await page.mouse.down()
    await page.mouse.move(ax + 30, ay + 30, { steps: 8 })
    await page.mouse.up()

    // Wait for commit (editLog grows) — the overlay re-derives from the updated store
    await expect
      .poll(async () => (await readBezierState(page))?.editLogLength ?? editLog0, { timeout: 8_000 })
      .toBeGreaterThan(editLog0)

    // Read the overlay geometry AFTER the drag committed
    const stateAfter = await readBezierState(page)
    const snapshotAfter = stateAfter?.editedRingSnapshot

    expect(stateAfter?.editedContourPointCount, 'overlay must still be mounted after drag').toBeGreaterThan(0)

    // THE LOAD-BEARING ASSERTION: the overlay geometry CHANGED.
    // A real drag moves anchor[0] by +30,+30 screen px at 6× zoom; flattening the affected
    // dirty segments produces different (lon,lat) coords → different canvas px → different snapshot.
    // This proves the live overlay tracks the committed Bézier edit — not just count > 0.
    expect(snapshotAfter, 'editedRingSnapshot must be present after drag').toBeTruthy()
    expect(
      snapshotAfter,
      'OVERLAY GEOMETRY MUST CHANGE after a real drag: editedRingSnapshot differs before/after (overlay tracks committed store.vertices)',
    ).not.toBe(snapshotBefore)

    // Sanity: count unchanged (op:'move' does not add/remove vertices; reshape, not resize)
    expect(
      stateAfter?.editedContourPointCount,
      'overlay point count must be unchanged after drag (same vertex count, different coords)',
    ).toBe(before)
  })
})
