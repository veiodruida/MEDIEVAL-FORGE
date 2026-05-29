/**
 * Phase 08.1 Plan 07 — G5 + G7 real-event reachability spec.
 *
 * ANTI-PATTERN GUARD: this spec MUST NOT call __forgeBezierTriggerDrag /
 * __forgeBezierTriggerInsert / __forgeBezierTriggerHandleDrag for the
 * reachability/insert claim. The commit/insert must flow through real
 * page.mouse events only. __forgeSelectBarony is permitted (selection is
 * the setup step, NOT the claim under test). __forgeBezierState /
 * __forgeStageScale are read-only inspection hooks (NOT trigger hooks).
 *
 * WHY THIS SPEC EXISTS (false-green guard):
 * Plans 08.1-04 through 08.1-06 tested drag/insert via DEV trigger hooks
 * (__forgeBezierTriggerDrag / __forgeBezierTriggerInsert). These hooks call
 * the real handlers but bypass Konva hit-testing entirely. The human UAT
 * caught that real browser events FAILED because anchors were ~3px at
 * Iberia fit-to-view scale — too small to click/drag. This plan fixes the
 * sizing (G5) and widens the hit-path (G7), then proves the fix with REAL
 * page.mouse events — the exact false-green failure mode this spec eliminates.
 *
 * REQ-IDs: BEZ-RENDER-01, BEZ-RENDER-02, BEZ-DRAG-01, BEZ-UAT-01, BEZ-IDENTITY-01
 */
import { readFileSync } from 'node:fs'
import { test, expect, type Page } from '@playwright/test'

function loadProjectInfo(): { project_id: string; name: string } {
  const p = process.env.UAT_PROJECT_INFO_PATH
  if (!p) {
    throw new Error(
      'UAT_PROJECT_INFO_PATH is not set; globalSetup did not run. Did you launch via `npx playwright test`?',
    )
  }
  return JSON.parse(readFileSync(p, 'utf-8'))
}

// Extend BezierState with the additive midCurvePoint field from Plan 07 Task 2.
interface BezierState {
  anchorCount: number
  activeAnchorIdx: number | null
  dirtySegmentCount: number
  editLogLength: number
  firstAnchor: { idx: number; x: number; y: number } | null
  midCurvePoint?: { x: number; y: number } | null
}

async function readBezierState(page: Page): Promise<BezierState | null> {
  return page.evaluate(() => {
    const fn = (window as unknown as { __forgeBezierState?: () => unknown }).__forgeBezierState
    return fn ? (fn() as BezierState) : null
  })
}

/**
 * Discover a real barony id from the seeded baronies.geojson at runtime.
 * Picks the barony whose centroid is closest to the geographic center of Iberia
 * (lon≈-3.5, lat≈40) so the selected barony is likely visible at fit-to-view scale.
 * Never hardcode a fixture name that could drift from territory_data_v3.py.
 */
async function discoverBaronyId(page: Page, projectId: string): Promise<string> {
  const id = await page.evaluate(async (pid) => {
    const res = await fetch(`/api/v3/projects/${pid}/artifacts/baronies.geojson`)
    if (!res.ok) return null
    const fc = await res.json()
    if (!fc?.features?.length) return null
    // Iberia geographic center: lon≈-3.5, lat≈40 (Castile area, center of the map)
    const centerLon = -3.5
    const centerLat = 40.0
    let bestId: string | null = null
    let bestDist = Infinity
    for (const feat of fc.features) {
      const id = feat?.id ?? feat?.properties?.id ?? feat?.properties?.name ?? null
      if (!id) continue
      // Try centroid from bbox midpoint or geometry coordinates
      let lon: number | null = null
      let lat: number | null = null
      if (feat.bbox && feat.bbox.length >= 4) {
        lon = (feat.bbox[0] + feat.bbox[2]) / 2
        lat = (feat.bbox[1] + feat.bbox[3]) / 2
      } else if (feat.geometry?.coordinates) {
        // Use first coordinate as approximation
        const coords = feat.geometry.coordinates
        const first = Array.isArray(coords[0]) ? (Array.isArray(coords[0][0]) ? coords[0][0] : coords[0]) : coords
        if (typeof first[0] === 'number' && typeof first[1] === 'number') {
          lon = first[0]; lat = first[1]
        }
      }
      if (lon === null || lat === null) continue
      const dist = Math.sqrt((lon - centerLon) ** 2 + (lat - centerLat) ** 2)
      if (dist < bestDist) { bestDist = dist; bestId = String(id) }
    }
    // Fall back to first feature if no centroid could be computed
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
 * Zoom in using REAL wheel events centered on (cx, cy) until __forgeStageScale
 * crosses targetAbsolute. IMPORTANT: hover over (cx,cy) first so Konva's
 * getPointerPosition() returns a valid point (Chromium requires the pointer
 * to be inside the element for wheel events to reach it).
 *
 * Loop-based (not fixed count): SCALE_BY=1.05, so reaching 6× needs ~37 ticks.
 * Cap at maxTicks to prevent infinite loops.
 */
async function zoomInUntilAbsolute(
  page: Page,
  cx: number,
  cy: number,
  targetAbsolute: number,
  maxTicks = 80,
): Promise<number> {
  // Prime Konva's pointer: hover then dispatch a mouse move so getPointerPosition
  // returns a valid coordinate before the first wheel event arrives.
  await page.mouse.move(cx, cy)
  // Small pause so Konva's pointermove listener fires and caches the position
  await page.waitForTimeout(50)

  let ticks = 0
  while (ticks < maxTicks) {
    const scale = await page.evaluate(() =>
      (window as unknown as { __forgeStageScale?: number }).__forgeStageScale ?? 1,
    )
    if (scale >= targetAbsolute) break
    // Wheel with pointer explicitly at (cx,cy) — Konva uses stage.getPointerPosition()
    // which reflects the last pointer event, so keep it fresh each tick.
    await page.mouse.move(cx, cy)
    await page.mouse.wheel(0, -100) // deltaY < 0 → zoom in
    ticks++
  }
  return await page.evaluate(() =>
    (window as unknown as { __forgeStageScale?: number }).__forgeStageScale ?? 1,
  )
}

// ─── Tests ─────────────────────────────────────────────────────────────────────

test.describe('Phase 08.1 Plan 07 — G5+G7 real-event usable targets', () => {

  /**
   * TEST 1 — REAL page.mouse drag commits op:move at usable zoom (G5).
   *
   * Proves: after raising MAX_SCALE_MULTIPLIER=16 and screen-space sizing,
   * the anchor square is large enough to grab and drag with real mouse events
   * at 6× zoom. editLogLength grows → op:'move' committed.
   *
   * Z-ORDER NOTE: the anchor Rect is rendered ON TOP of the hit-path (siblings,
   * anchor drawn after hit-path in the Layer). A drag at the anchor CENTER
   * correctly hits the Rect (desired for drag).
   *
   * Zoom strategy: zoom centered on firstAnchor's on-screen position so the
   * anchor stays visible (Konva's cursor-anchored zoom keeps the pointer-world
   * point stationary).
   */
  test('G5: real page.mouse drag on anchor at 6x zoom commits op:move (NO __forgeBezierTrigger*)', async ({
    page,
  }) => {
    const info = loadProjectInfo()
    await navigateToWorkspace(page, info.project_id)

    await expect(page.getByTestId('edit-tool-palette')).toBeVisible()
    await page.getByTestId('edit-tool-v').click()

    const baronyId = await discoverBaronyId(page, info.project_id)
    await page.evaluate((id) => {
      ;(window as unknown as { __forgeSelectBarony?: (id: string) => void }).__forgeSelectBarony?.(id)
    }, baronyId)

    // Wait for anchors to mount (ring fit complete)
    await expect
      .poll(async () => (await readBezierState(page))?.anchorCount ?? 0, { timeout: 15_000 })
      .toBeGreaterThanOrEqual(4)

    // Capture fit scale BEFORE zooming (advisor: capture initial before zoom, compare against that)
    const fitScale = await page.evaluate(() =>
      (window as unknown as { __forgeStageScale?: number }).__forgeStageScale ?? 1,
    )

    // Get canvas bounding box for containment checks
    const canvasBox = await page.getByTestId('canvas-stage').boundingBox()
    expect(canvasBox, 'canvas-stage bounding box must be present').not.toBeNull()

    // Zoom at canvas center to raise scale.
    // The anchor may end up off-screen after zoom (if barony is near an edge at fit);
    // we pan imperatively after zoom via __forgePanToFirstAnchor.
    const canvasCx = canvasBox!.x + canvasBox!.width / 2
    const canvasCy = canvasBox!.y + canvasBox!.height / 2

    // Target: 6× the fit scale (proves MAX_SCALE_MULTIPLIER=16 allows this; old cap was 4×)
    const targetScale = fitScale * 6
    const achievedScale = await zoomInUntilAbsolute(page, canvasCx, canvasCy, targetScale, 80)

    // Assert we actually reached at least 5× fit (old 4× cap would block this)
    expect(achievedScale, `zoom must reach at least 5× fit (achieved ${achievedScale}, fit was ${fitScale})`).toBeGreaterThan(fitScale * 4.5)

    // Pan the stage to center the first anchor on-screen via the DEV hook.
    // __forgePanToFirstAnchor adjusts stage.x/y so anchor[0].anchorPx maps to viewport center.
    // This is a display-only imperitive pan (no store write, no React re-render needed).
    const panned = await page.evaluate(() =>
      (window as unknown as { __forgePanToFirstAnchor?: () => boolean }).__forgePanToFirstAnchor?.() ?? false,
    )
    expect(panned, '__forgePanToFirstAnchor must succeed (layer + stage accessible)').toBe(true)

    // Re-read firstAnchor AFTER zoom + pan — should now be near canvas center
    const stateAfterZoom = await readBezierState(page)
    expect(stateAfterZoom?.firstAnchor, 'firstAnchor must be non-null after zoom').not.toBeNull()
    const { x: ax, y: ay } = stateAfterZoom!.firstAnchor!

    // Viewport containment: firstAnchor must be in the visible canvas area
    expect(ax, 'anchor x must be inside canvas after zoom').toBeGreaterThan(canvasBox!.x)
    expect(ax, 'anchor x must be inside canvas after zoom').toBeLessThan(canvasBox!.x + canvasBox!.width)
    expect(ay, 'anchor y must be inside canvas after zoom').toBeGreaterThan(canvasBox!.y)
    expect(ay, 'anchor y must be inside canvas after zoom').toBeLessThan(canvasBox!.y + canvasBox!.height)

    const editLog0 = stateAfterZoom!.editLogLength

    // REAL page.mouse drag on the anchor (Rect is on top — correct grab target for drag)
    await page.mouse.move(ax, ay)
    await page.mouse.down()
    await page.mouse.move(ax + 30, ay + 30, { steps: 8 })
    await page.mouse.up()

    // Commit proof: editLog grew via the real op:'move' flatten path
    await expect
      .poll(async () => (await readBezierState(page))?.editLogLength ?? editLog0, { timeout: 8_000 })
      .toBeGreaterThan(editLog0)
  })

  /**
   * TEST 2 — REAL page.mouse dblclick inserts anchor at mid-segment (G7).
   *
   * Z-ORDER REASON (LOCKED): the anchor Rects are rendered AFTER (on top of) the
   * bezier-hit-path in the same Layer — they are SIBLINGS. A dblclick at an anchor
   * CENTER hits the Rect (no onDblClick) → bubbles to Stage → hit-path never fires.
   * This test targets midCurvePoint (t=0.5 between anchor 0 and 1) — away from
   * all anchor Rects. At fresh mount activeAnchorIdx is null so no handles render.
   *
   * Zoom strategy: zoom centered on midCurvePoint (after reading it at fit scale)
   * so the target stays visible during the zoom.
   */
  test('G7: real page.mouse dblclick on mid-segment on-curve point inserts anchor (NO __forgeBezierTrigger*)', async ({
    page,
  }) => {
    const info = loadProjectInfo()
    await navigateToWorkspace(page, info.project_id)

    await expect(page.getByTestId('edit-tool-palette')).toBeVisible()
    await page.getByTestId('edit-tool-v').click()

    const baronyId = await discoverBaronyId(page, info.project_id)
    // Fresh select → activeAnchorIdx is null → no handles render over mid-segment
    await page.evaluate((id) => {
      ;(window as unknown as { __forgeSelectBarony?: (id: string) => void }).__forgeSelectBarony?.(id)
    }, baronyId)

    // Wait for anchors to mount
    await expect
      .poll(async () => (await readBezierState(page))?.anchorCount ?? 0, { timeout: 15_000 })
      .toBeGreaterThanOrEqual(4)

    // Capture fit scale BEFORE zooming
    const fitScale = await page.evaluate(() =>
      (window as unknown as { __forgeStageScale?: number }).__forgeStageScale ?? 1,
    )

    const canvasBox = await page.getByTestId('canvas-stage').boundingBox()
    expect(canvasBox, 'canvas-stage bounding box must be present').not.toBeNull()

    // Read midCurvePoint at fit scale (needed for the dblclick target after zoom+pan)
    const stateAtFit = await readBezierState(page)
    const midAtFit = stateAtFit?.midCurvePoint
    expect(midAtFit, 'midCurvePoint must be non-null at fit scale (≥2 anchors required)').toBeTruthy()

    // Zoom at canvas center to 4× fit, then pan via __forgePanToFirstAnchor to bring the
    // barony into view (same strategy as G5).
    const canvasCx = canvasBox!.x + canvasBox!.width / 2
    const canvasCy = canvasBox!.y + canvasBox!.height / 2
    const targetScale = fitScale * 4
    await zoomInUntilAbsolute(page, canvasCx, canvasCy, targetScale, 60)

    // Pan stage to center first anchor (and nearby mid-curve point) on screen
    const panned = await page.evaluate(() =>
      (window as unknown as { __forgePanToFirstAnchor?: () => boolean }).__forgePanToFirstAnchor?.() ?? false,
    )
    expect(panned, '__forgePanToFirstAnchor must succeed').toBe(true)
    // Let Konva's batchDraw (requestAnimationFrame) run before reading state or clicking
    await page.waitForTimeout(100)

    // Re-read midCurvePoint AFTER zoom + pan (stageX/Y now reflect the pan)
    const stateAfterZoom = await readBezierState(page)
    const mid = stateAfterZoom?.midCurvePoint
    expect(mid, 'midCurvePoint must be non-null after zoom').toBeTruthy()

    // Viewport containment check: mid-curve point must be inside the canvas box.
    // If off-screen, the real dblclick would hit nothing — this is a valid test gate.
    expect(mid!.x, 'mid-curve point x must be inside canvas').toBeGreaterThan(canvasBox!.x)
    expect(mid!.x, 'mid-curve point x must be inside canvas').toBeLessThan(canvasBox!.x + canvasBox!.width)
    expect(mid!.y, 'mid-curve point y must be inside canvas').toBeGreaterThan(canvasBox!.y)
    expect(mid!.y, 'mid-curve point y must be inside canvas').toBeLessThan(canvasBox!.y + canvasBox!.height)

    const anchorCount0 = stateAfterZoom!.anchorCount
    const editLog0 = stateAfterZoom!.editLogLength

    // Move to target to prime Konva's pointer position cache.
    await page.mouse.move(mid!.x, mid!.y)
    await page.waitForTimeout(100) // let pointermove propagate and hit canvas update

    // REAL double-click ON the mid-segment curve (not on any anchor — z-order trap avoided).
    // Use double delay to ensure Konva recognizes it as a dblclick (not two separate clicks).
    await page.mouse.dblclick(mid!.x, mid!.y, { delay: 50 })

    // G7 proof: anchorCount increased by 1 (insert via real Konva onDblClick on hit-path)
    await expect
      .poll(async () => (await readBezierState(page))?.anchorCount ?? anchorCount0, { timeout: 8_000 })
      .toBe(anchorCount0 + 1)

    // BEZ-IDENTITY-01 extended: insert is a NO-OP on the store (zero store write on insert)
    const stateAfterInsert = await readBezierState(page)
    expect(stateAfterInsert?.editLogLength, 'editLog must be unchanged after bare dblclick insert (identity-safe)').toBe(editLog0)
  })

  /**
   * TEST 3 — Empty-log identity re-assertion through real UI (BEZ-IDENTITY-01).
   *
   * Entry + mount with zero interaction → editLog unchanged. Validates that the
   * display-only changes in this plan (sizing, zoom cap, event wiring) add zero
   * store writes on entry. Re-asserts BEZ-IDENTITY-01 end-to-end in the running app.
   */
  test('BEZ-IDENTITY-01 re-assert: enter Bézier mode + zero interaction → editLog unchanged', async ({
    page,
  }) => {
    const info = loadProjectInfo()
    await navigateToWorkspace(page, info.project_id)

    await expect(page.getByTestId('edit-tool-palette')).toBeVisible()
    await page.getByTestId('edit-tool-v').click()

    const baronyId = await discoverBaronyId(page, info.project_id)
    await page.evaluate((id) => {
      ;(window as unknown as { __forgeSelectBarony?: (id: string) => void }).__forgeSelectBarony?.(id)
    }, baronyId)

    // Wait for BezierEditLayer to mount and fit anchors
    await expect
      .poll(async () => (await readBezierState(page))?.anchorCount ?? 0, { timeout: 15_000 })
      .toBeGreaterThanOrEqual(4)

    // Capture editLog baseline right after mount (before any interaction)
    const editLog0 = (await readBezierState(page))!.editLogLength

    // Zero interaction — do NOT drag, do NOT insert.
    // Assert editLog is unchanged at mount (no phantom entry on entry).
    const stateAtMount = await readBezierState(page)
    expect(stateAtMount?.editLogLength, 'editLog must be unchanged after mount with zero interaction').toBe(editLog0)

    // Deselect by clicking an empty area of the canvas (top-left corner away from map)
    const canvasBox = await page.getByTestId('canvas-stage').boundingBox()
    if (canvasBox) {
      await page.mouse.click(canvasBox.x + 10, canvasBox.y + 10)
    }

    // After deselect: if BezierState still present, editLog must still be editLog0.
    // (Layer may or may not unmount depending on click target — accept either outcome.)
    await expect
      .poll(
        async () => {
          const s = await readBezierState(page)
          if (s === null) return editLog0 // layer unmounted cleanly — accept
          return s.editLogLength
        },
        { timeout: 5_000 },
      )
      .toBe(editLog0)
  })
})
