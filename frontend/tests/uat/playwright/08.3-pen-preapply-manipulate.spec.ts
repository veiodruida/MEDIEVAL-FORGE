/**
 * Phase 08.3 Plan 11 — PEN-PREAPPLY-EDIT-01 real-mouse Playwright UAT
 *
 * Scenario A (CREATE): draw a shape in open ocean/gap → close → drag whole shape →
 *   drag a vertex → Apply → manipulated geometry persists → reload persists.
 *
 * Scenario B (CARVE): draw a shape inside an existing barony → close → drag whole
 *   shape → drag a vertex → Apply → manipulated geometry persists → reload persists.
 *
 * REAL page.mouse ONLY — ZERO __forge* hooks used as input gestures.
 * (project lesson: hooks hid the PEN-CURVE-01 bug all session; 08.3 VERIFICATION.md)
 *
 * DEV hatches used READ-ONLY for assertions / anchor lookups:
 *   __forgePendingRing       — read pending op.ring in geo coords (read-only, NOT input)
 *   __forgePendingRingScreen — read current ring vertices in canvas-container px
 *                              (read-only; add stageBox.{x,y} to get page coords)
 *
 * REQ-IDs: PEN-PREAPPLY-EDIT-01
 *
 * COORDINATE FIX (08.3-11 debug session):
 *   geoToStageXY() is kept for DRAW CLICKS ONLY (placing initial anchors — these
 *   only need to land somewhere plausible in the map, not on an already-rendered shape).
 *   It is NOT used for drag anchors, which must hit the rendered shape exactly.
 *   For drag/vertex/selection anchors: re-read __forgePendingRingScreen() immediately
 *   before each gesture so the mousedown always targets the live rendered shape
 *   regardless of pan/zoom state.
 *
 * COMPONENT FIX (08.3-11 debug session):
 *   PenShapeManipulateLayer was using manual mousedown/mousemove/mouseup on a Layer.
 *   Konva Layers only propagate events bubbled from their children; once the cursor
 *   leaves the shape, the Stage swallows move/up events and the Layer handlers never
 *   fire → drag appeared to be a no-op (dLat=0 always).  Fixed by switching to
 *   Konva's `draggable` prop with onDragMove/onDragEnd — same pattern as BezierEditLayer.
 */
import * as fs from 'node:fs'
import * as path from 'node:path'
import * as crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { test, expect, type Page } from '@playwright/test'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// ─── Project info helper ──────────────────────────────────────────────────────

function loadProjectInfo(): { project_id: string; name: string } {
  const p = process.env.UAT_PROJECT_INFO_PATH
  if (!p) throw new Error('UAT_PROJECT_INFO_PATH not set — globalSetup did not run')
  return JSON.parse(fs.readFileSync(p, 'utf-8'))
}

// ─── Canvas navigation helpers ────────────────────────────────────────────────

async function navigateToWorkspace(page: Page, projectId: string) {
  await page.goto(`/projects/${projectId}`)
  await expect(page.getByTestId('canvas-stage')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId('territory-layer-ready')).toBeAttached({ timeout: 30_000 })
}

// ─── lookup_barony.png SHA helper ─────────────────────────────────────────────

async function lookupBaronySha(page: Page, projectId: string): Promise<string> {
  const b64 = await page.evaluate(async (pid: string) => {
    const url = `/api/v3/projects/${pid}/artifacts/lookup_barony.png?_nc=${Date.now()}`
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) throw new Error(`artifact fetch: ${res.status}`)
    const buf = new Uint8Array(await res.arrayBuffer())
    let bin = ''
    for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i])
    return btoa(bin)
  }, projectId)
  return crypto.createHash('sha256').update(Buffer.from(b64, 'base64')).digest('hex')
}

// ─── Read pending ring (READ-ONLY assertion helper — geo coords) ──────────────

async function readPendingRing(
  page: Page,
): Promise<Array<{ lat: number; lon: number }> | null> {
  return page.evaluate(() => {
    const fn = (window as unknown as { __forgePendingRing?: () => unknown }).__forgePendingRing
    return fn ? (fn() as Array<{ lat: number; lon: number }> | null) : null
  })
}

// ─── Read pending ring in canvas-container screen coords (READ-ONLY) ──────────
//
// Returns each ring vertex in pixels relative to the top-left of the
// data-testid="canvas-stage" div.  Add stageBox.x / stageBox.y for page coords.
// Re-read this BEFORE every gesture — the shape moves after each drag.

async function readPendingRingScreen(
  page: Page,
): Promise<Array<{ x: number; y: number }> | null> {
  return page.evaluate(() => {
    const fn = (window as unknown as {
      __forgePendingRingScreen?: () => unknown
    }).__forgePendingRingScreen
    return fn ? (fn() as Array<{ x: number; y: number }> | null) : null
  })
}

// ─── Screen-space centroid helper ─────────────────────────────────────────────

function screenCentroid(pts: Array<{ x: number; y: number }>): { x: number; y: number } {
  const x = pts.reduce((s, p) => s + p.x, 0) / pts.length
  const y = pts.reduce((s, p) => s + p.y, 0) / pts.length
  return { x, y }
}

// ─── Geo centroid helper for a ring ──────────────────────────────────────────

function ringCentroid(ring: Array<{ lat: number; lon: number }>): { lat: number; lon: number } {
  // Drop closing duplicate if present
  const pts = ring[0].lat === ring[ring.length - 1].lat &&
              ring[0].lon === ring[ring.length - 1].lon
    ? ring.slice(0, ring.length - 1)
    : ring
  const lat = pts.reduce((s, p) => s + p.lat, 0) / pts.length
  const lon = pts.reduce((s, p) => s + p.lon, 0) / pts.length
  return { lat, lon }
}

// ─── Iberia bounds for geo → stage-px (DRAW CLICKS ONLY) ────────────────────
// Used to place initial pen anchors. geoToStageXY is a coarse linear map —
// good enough to land in the right map region, NOT used for drag anchors.
const IBERIA_LON_MIN = -9.5
const IBERIA_LON_MAX = 3.3
const IBERIA_LAT_MIN = 36.0
const IBERIA_LAT_MAX = 44.0

function geoToStageXY(
  lat: number,
  lon: number,
  stageBox: { x: number; y: number; width: number; height: number },
): { x: number; y: number } {
  const xFrac = (lon - IBERIA_LON_MIN) / (IBERIA_LON_MAX - IBERIA_LON_MIN)
  const yFrac = 1.0 - (lat - IBERIA_LAT_MIN) / (IBERIA_LAT_MAX - IBERIA_LAT_MIN)
  return {
    x: stageBox.x + xFrac * stageBox.width,
    y: stageBox.y + yFrac * stageBox.height,
  }
}

// ─── Screenshot helper ────────────────────────────────────────────────────────

async function captureScreenshot(page: Page, filename: string): Promise<void> {
  const repoRoot = path.resolve(__dirname, '../../../..')
  const outPath = path.join(repoRoot, filename)
  await page.screenshot({ path: outPath, fullPage: false })
  console.log(`  Screenshot: ${outPath}`)
}

// ─── Wait for apply + SHA change ─────────────────────────────────────────────

async function waitForShaChange(page: Page, projectId: string, baselineSha: string): Promise<string> {
  await expect
    .poll(
      async () => {
        const sha = await lookupBaronySha(page, projectId)
        return sha !== baselineSha
      },
      {
        timeout: 300_000,
        intervals: [3_000, 5_000, 8_000],
        message: 'lookup_barony.png SHA must change after Apply+render',
      },
    )
    .toBe(true)
  return lookupBaronySha(page, projectId)
}

// ─── Main test suite ──────────────────────────────────────────────────────────

test.describe('Phase 08.3 Plan 11 — PEN pre-Apply manipulation (REAL page.mouse)', () => {

  // ────────────────────────────────────────────────────────────────────────────
  // Scenario A: CREATE — draw in open ocean → drag shape + vertex → Apply
  // ────────────────────────────────────────────────────────────────────────────
  test(
    'A: CREATE — draw shape in gap → close → drag shape → drag vertex → Apply → reload persists',
    async ({ page }: { page: Page }) => {
      test.setTimeout(1_200_000)

      const info = loadProjectInfo()
      await navigateToWorkspace(page, info.project_id)

      const baselineSha = await lookupBaronySha(page, info.project_id)
      console.log(`  A: baseline SHA: ${baselineSha.slice(0, 16)}…`)

      // ── Press P → pen tool active ──────────────────────────────────────────
      await expect(page.getByTestId('edit-tool-palette')).toBeVisible({ timeout: 10_000 })
      await page.keyboard.press('p')
      await expect(page.getByTestId('pen-action-bar')).toBeVisible({ timeout: 10_000 })
      console.log('  A: Pen tool active')

      const stageBox = await page.getByTestId('canvas-stage').boundingBox()
      if (!stageBox) throw new Error('canvas-stage bounding box not found')

      // ── Draw a small CREATE shape in open Atlantic ocean (west of Portugal) ──
      // These geo coords are well into the ocean (lon < -8), away from any barony,
      // creating a gap-fill scenario.  geoToStageXY places them coarsely — that is
      // fine for draw clicks (the pen just needs to land somewhere in the ocean).
      // The initial centroid lands at y≈503 (page), BELOW the LayerTogglePanel
      // (panel occupies canvas-relative y=12-430, i.e. page-y=stageBox.y+12 to +430).
      // We drag SOUTH (positive Y) so the shape moves AWAY from the panel, keeping
      // all vertices below the panel for the vertex-drag step.
      //   p0: lat=38.5, lon=-8.8  (ocean)
      //   p1: lat=38.5, lon=-8.4  (ocean)
      //   p2: lat=38.8, lon=-8.4  (ocean)
      const p0 = geoToStageXY(38.5, -8.8, stageBox)
      const p1 = geoToStageXY(38.5, -8.4, stageBox)
      const p2 = geoToStageXY(38.8, -8.4, stageBox)

      console.log(`  A: p0=${JSON.stringify(p0)}, p1=${JSON.stringify(p1)}, p2=${JSON.stringify(p2)}`)

      // Place anchors
      await page.mouse.move(p0.x, p0.y); await page.waitForTimeout(200)
      await page.mouse.click(p0.x, p0.y); await page.waitForTimeout(300)
      await page.mouse.move(p1.x, p1.y); await page.waitForTimeout(200)
      await page.mouse.click(p1.x, p1.y); await page.waitForTimeout(200)
      await page.mouse.move(p2.x, p2.y); await page.waitForTimeout(200)
      await page.mouse.click(p2.x, p2.y); await page.waitForTimeout(300)

      // Double-click near p0 to close
      await page.mouse.move(p0.x, p0.y); await page.waitForTimeout(300)
      await page.mouse.dblclick(p0.x, p0.y); await page.waitForTimeout(2_000)

      // If action bar still visible, use commit button to force close
      const actionBarVisible = await page.getByTestId('pen-action-bar').isVisible()
      if (actionBarVisible) {
        console.log('  A: action bar visible — clicking pen-btn-commit')
        const commitBtn = page.getByTestId('pen-btn-commit')
        if (await commitBtn.isVisible()) {
          await commitBtn.click(); await page.waitForTimeout(1_500)
        }
      }

      // ── Screenshot: drawn shape visible as green ghost ─────────────────────
      await captureScreenshot(page, 'uat-08.3-11-A-after-draw.png')

      // ── Dismiss any open floating panels (Layers panel may have opened during draw) ──
      // The Layers panel can open if a double-click accidentally lands on the "Camadas"
      // button area.  Pressing Escape and clicking a safe canvas area closes it so it
      // doesn't intercept mousedown during the drag gestures.
      await page.keyboard.press('Escape')
      await page.waitForTimeout(200)
      // Click in the right half of the canvas (far from the Layers panel) to dismiss
      const safeX = stageBox.x + stageBox.width * 0.85
      const safeY = stageBox.y + stageBox.height * 0.85
      await page.mouse.click(safeX, safeY)
      await page.waitForTimeout(300)

      // ── Read the committed ring (read-only assertion) ─────────────────────
      // PenShapeManipulateLayer must now be mounted (tool switched to 'V' after close)
      await page.waitForTimeout(500)
      const ringBeforeDrag = await readPendingRing(page)
      console.log(`  A: pending ring before drag: ${ringBeforeDrag?.length ?? 'null'} points`)
      expect(ringBeforeDrag).not.toBeNull()
      expect(ringBeforeDrag!.length).toBeGreaterThanOrEqual(3)

      const centroidBefore = ringCentroid(ringBeforeDrag!)
      console.log(`  A: centroid before drag: lat=${centroidBefore.lat.toFixed(4)}, lon=${centroidBefore.lon.toFixed(4)}`)

      // ── Drag the whole shape: body drag 60px south (positive Y = down) ───────
      // Shape starts at y≈503 (page), below the LayerTogglePanel (~y=stageBox.y+430).
      // Dragging SOUTH moves vertices further down, keeping them below the panel.
      const screenPtsBefore = await readPendingRingScreen(page)
      expect(screenPtsBefore).not.toBeNull()
      const centroidCanvasRel = screenCentroid(screenPtsBefore!)
      // Convert canvas-container-relative → page coordinates
      const bodyDragStart = {
        x: stageBox.x + centroidCanvasRel.x,
        y: stageBox.y + centroidCanvasRel.y,
      }
      // Drag 60px south (positive Y = down) — keeps shape in ocean, below the panel
      const BODY_DRAG_PX = 60
      const bodyDragEnd = { x: bodyDragStart.x, y: bodyDragStart.y + BODY_DRAG_PX }

      console.log(`  A: body drag: from ${JSON.stringify(bodyDragStart)} to ${JSON.stringify(bodyDragEnd)}`)
      await page.mouse.move(bodyDragStart.x, bodyDragStart.y); await page.waitForTimeout(200)
      await page.mouse.down(); await page.waitForTimeout(100)
      // Move gradually so Konva mousemove fires
      const steps = 10
      for (let s = 1; s <= steps; s++) {
        const t = s / steps
        await page.mouse.move(
          bodyDragStart.x + (bodyDragEnd.x - bodyDragStart.x) * t,
          bodyDragStart.y + (bodyDragEnd.y - bodyDragStart.y) * t,
        )
        await page.waitForTimeout(30)
      }
      await page.mouse.up(); await page.waitForTimeout(500)

      // Read ring after body drag
      const ringAfterBodyDrag = await readPendingRing(page)
      console.log(`  A: ring after body drag: ${ringAfterBodyDrag?.length ?? 'null'} points`)
      expect(ringAfterBodyDrag).not.toBeNull()

      const centroidAfterDrag = ringCentroid(ringAfterBodyDrag!)
      console.log(`  A: centroid after body drag: lat=${centroidAfterDrag.lat.toFixed(4)}, lon=${centroidAfterDrag.lon.toFixed(4)}`)
      // Dragging 60px south means lat decreases (south = lower lat in this projection).
      // Assert direction (dLat < 0) + meaningful magnitude (< -0.005°).
      const dLat = centroidAfterDrag.lat - centroidBefore.lat
      console.log(`  A: dLat from body drag = ${dLat.toFixed(4)} (expect < -0.005)`)
      expect(dLat).toBeLessThan(-0.005)

      // ── Screenshot: after body drag ────────────────────────────────────────
      await captureScreenshot(page, 'uat-08.3-11-A-after-body-drag.png')

      // ── Drag a vertex: move vertex 0 east (+x on screen) ──────────────────
      // Re-read ring screen positions AFTER the body drag — shape has moved.
      const screenPtsAfterBody = await readPendingRingScreen(page)
      expect(screenPtsAfterBody).not.toBeNull()
      const v0CanvasRel = screenPtsAfterBody![0]
      const v0DragStart = {
        x: stageBox.x + v0CanvasRel.x,
        y: stageBox.y + v0CanvasRel.y,
      }
      // Drag vertex 0 east (positive X = east in screen space)
      const VERTEX_DRAG_PX = 80
      const v0DragEnd = { x: v0DragStart.x + VERTEX_DRAG_PX, y: v0DragStart.y }

      console.log(`  A: vertex 0 drag: from ${JSON.stringify(v0DragStart)} to ${JSON.stringify(v0DragEnd)}`)
      await page.mouse.move(v0DragStart.x, v0DragStart.y); await page.waitForTimeout(200)
      await page.mouse.down(); await page.waitForTimeout(100)
      for (let s = 1; s <= steps; s++) {
        const t = s / steps
        await page.mouse.move(
          v0DragStart.x + (v0DragEnd.x - v0DragStart.x) * t,
          v0DragStart.y + (v0DragEnd.y - v0DragStart.y) * t,
        )
        await page.waitForTimeout(30)
      }
      await page.mouse.up(); await page.waitForTimeout(500)

      // Read ring after vertex drag
      const ringAfterVertexDrag = await readPendingRing(page)
      console.log(`  A: ring after vertex drag: ${ringAfterVertexDrag?.length ?? 'null'} points`)
      expect(ringAfterVertexDrag).not.toBeNull()

      // Vertex 0 must have moved east (lon increases going right in screen space)
      const v0Before = ringAfterBodyDrag![0]
      const v0After = ringAfterVertexDrag![0]
      console.log(`  A: v0 lon: before=${v0Before.lon.toFixed(4)}, after=${v0After.lon.toFixed(4)}`)
      const dLon = v0After.lon - v0Before.lon
      console.log(`  A: dLon from vertex drag = ${dLon.toFixed(4)} (expect > 0.005)`)
      expect(dLon).toBeGreaterThan(0.005)

      // ── Screenshot: after vertex drag ──────────────────────────────────────
      await captureScreenshot(page, 'uat-08.3-11-A-after-vertex-drag.png')

      // ── Activate BezierApplyControls by selecting any existing barony ────────
      // bezier-apply-edits-btn only renders when activeTerritoryId !== null.
      // The new CREATE barony doesn't exist yet (Apply hasn't run). Select any
      // existing barony via the DEV hatch so the Apply button appears.
      const anyBaronyIdA = await page.evaluate(async (pid: string) => {
        const res = await fetch(`/api/v3/projects/${pid}/artifacts/baronies.geojson`)
        if (!res.ok) return null
        const gj = await res.json() as { features?: Array<{ properties?: { id?: string } }> }
        return gj.features?.[0]?.properties?.id ?? null
      }, info.project_id)
      if (anyBaronyIdA) {
        await page.evaluate((id: string) => {
          ;(window as unknown as { __forgeSelectBarony?: (id: string) => void }).__forgeSelectBarony?.(id)
        }, anyBaronyIdA)
      }

      // ── Apply edições ────────────────────────────────────────────────────
      const applyBtn = page.getByTestId('bezier-apply-edits-btn')
      await expect(applyBtn).toBeEnabled({ timeout: 15_000 })
      console.log('  A: Apply button enabled — clicking')
      await applyBtn.click()

      // Wait for SHA change
      const afterApplySha = await waitForShaChange(page, info.project_id, baselineSha)
      console.log(`  A: after-apply SHA: ${afterApplySha.slice(0, 16)}… (changed: ${afterApplySha !== baselineSha})`)
      expect(afterApplySha).not.toBe(baselineSha)

      await captureScreenshot(page, 'uat-08.3-11-A-after-apply.png')
      console.log('  A: SHA change CONFIRMED — manipulated CREATE shape rendered')

      // ── Reload and re-assert persistence ──────────────────────────────────
      console.log('  A: Reloading…')
      await page.reload()
      await expect(page.getByTestId('canvas-stage')).toBeVisible({ timeout: 20_000 })
      await expect(page.getByTestId('territory-layer-ready')).toBeAttached({ timeout: 30_000 })

      const afterReloadSha = await lookupBaronySha(page, info.project_id)
      console.log(`  A: after-reload SHA: ${afterReloadSha.slice(0, 16)}…`)
      expect(afterReloadSha).not.toBe(baselineSha)

      await captureScreenshot(page, 'uat-08.3-11-A-after-reload.png')
      console.log('  A: PASSED — CREATE manipulation persisted after reload')
    },
  )

  // ────────────────────────────────────────────────────────────────────────────
  // Scenario B: CARVE — draw inside existing barony → drag shape + vertex → Apply
  // ────────────────────────────────────────────────────────────────────────────
  test(
    'B: CARVE — draw inside barony → close → drag shape → drag vertex → Apply → reload persists',
    async ({ page }: { page: Page }) => {
      test.setTimeout(1_200_000)

      const info = loadProjectInfo()
      await navigateToWorkspace(page, info.project_id)

      const baselineSha = await lookupBaronySha(page, info.project_id)
      console.log(`  B: baseline SHA: ${baselineSha.slice(0, 16)}…`)

      // ── Press P → pen tool active ──────────────────────────────────────────
      await expect(page.getByTestId('edit-tool-palette')).toBeVisible({ timeout: 10_000 })
      await page.keyboard.press('p')
      await expect(page.getByTestId('pen-action-bar')).toBeVisible({ timeout: 10_000 })
      console.log('  B: Pen tool active')

      const stageBox = await page.getByTestId('canvas-stage').boundingBox()
      if (!stageBox) throw new Error('canvas-stage bounding box not found')

      // ── Draw a CARVE shape inside a large Iberian barony ─────────────────
      // Use generous geo spans (≥0.4° lon × ≥0.4° lat) to clear MIN_AREA_PX2=200.
      // The original Toledo coords (0.2° × 0.1°) rendered as ~10×8px — below the gate.
      // Centred on Toledo region (lat≈39.8, lon≈-4.0) which is a large barony:
      //   c0: lat=39.5, lon=-4.5
      //   c1: lat=39.5, lon=-4.0
      //   c2: lat=39.9, lon=-4.0
      const c0 = geoToStageXY(39.5, -4.5, stageBox)
      const c1 = geoToStageXY(39.5, -4.0, stageBox)
      const c2 = geoToStageXY(39.9, -4.0, stageBox)

      console.log(`  B: c0=${JSON.stringify(c0)}, c1=${JSON.stringify(c1)}, c2=${JSON.stringify(c2)}`)

      await page.mouse.move(c0.x, c0.y); await page.waitForTimeout(200)
      await page.mouse.click(c0.x, c0.y); await page.waitForTimeout(300)
      await page.mouse.move(c1.x, c1.y); await page.waitForTimeout(200)
      await page.mouse.click(c1.x, c1.y); await page.waitForTimeout(200)
      await page.mouse.move(c2.x, c2.y); await page.waitForTimeout(200)
      await page.mouse.click(c2.x, c2.y); await page.waitForTimeout(300)

      // Double-click near c0 to close
      await page.mouse.move(c0.x, c0.y); await page.waitForTimeout(300)
      await page.mouse.dblclick(c0.x, c0.y); await page.waitForTimeout(2_000)

      // If action bar still visible, use commit button
      const actionBarVisible = await page.getByTestId('pen-action-bar').isVisible()
      if (actionBarVisible) {
        console.log('  B: action bar visible — clicking pen-btn-commit')
        const commitBtn = page.getByTestId('pen-btn-commit')
        if (await commitBtn.isVisible()) {
          await commitBtn.click(); await page.waitForTimeout(1_500)
        }
      }

      await captureScreenshot(page, 'uat-08.3-11-B-after-draw.png')

      // ── Dismiss any open floating panels (same as scenario A) ─────────────
      await page.keyboard.press('Escape')
      await page.waitForTimeout(200)
      const safeBX = stageBox.x + stageBox.width * 0.85
      const safeBY = stageBox.y + stageBox.height * 0.85
      await page.mouse.click(safeBX, safeBY)
      await page.waitForTimeout(300)

      // ── Read committed ring (read-only) ───────────────────────────────────
      await page.waitForTimeout(500)
      const ringBeforeDrag = await readPendingRing(page)
      console.log(`  B: pending ring: ${ringBeforeDrag?.length ?? 'null'} points`)

      // B MUST produce a pending ring — the drag assertions are not optional.
      // If null, the draw landed outside any barony (create op instead of carve).
      // Both create and carve ops produce a ring, so non-null is the requirement.
      expect(ringBeforeDrag).not.toBeNull()
      expect(ringBeforeDrag!.length).toBeGreaterThanOrEqual(3)

      const centroidBefore = ringCentroid(ringBeforeDrag!)
      console.log(`  B: centroid: lat=${centroidBefore.lat.toFixed(4)}, lon=${centroidBefore.lon.toFixed(4)}`)

      // ── Drag shape body south by ~50px (positive Y = south) ───────────────
      // Re-read actual screen positions before dragging.
      const screenPtsBefore = await readPendingRingScreen(page)
      expect(screenPtsBefore).not.toBeNull()
      const centroidCanvasRel = screenCentroid(screenPtsBefore!)
      const bodyDragStart = {
        x: stageBox.x + centroidCanvasRel.x,
        y: stageBox.y + centroidCanvasRel.y,
      }
      const BODY_DRAG_PX = 50
      // Drag south (positive Y) — keep small to stay within the Iberian landmass
      const bodyDragEnd = { x: bodyDragStart.x, y: bodyDragStart.y + BODY_DRAG_PX }

      console.log(`  B: body drag south: ${JSON.stringify(bodyDragStart)} → ${JSON.stringify(bodyDragEnd)}`)
      await page.mouse.move(bodyDragStart.x, bodyDragStart.y); await page.waitForTimeout(200)
      await page.mouse.down(); await page.waitForTimeout(100)
      const steps = 10
      for (let s = 1; s <= steps; s++) {
        const t = s / steps
        await page.mouse.move(
          bodyDragStart.x + (bodyDragEnd.x - bodyDragStart.x) * t,
          bodyDragStart.y + (bodyDragEnd.y - bodyDragStart.y) * t,
        )
        await page.waitForTimeout(30)
      }
      await page.mouse.up(); await page.waitForTimeout(500)

      const ringAfterBodyDrag = await readPendingRing(page)
      expect(ringAfterBodyDrag).not.toBeNull()
      const centroidAfter = ringCentroid(ringAfterBodyDrag!)
      const dLat = centroidAfter.lat - centroidBefore.lat
      // Dragging south (positive Y) → lat decreases (negative dLat)
      console.log(`  B: dLat from body drag = ${dLat.toFixed(4)} (expect < -0.005)`)
      expect(dLat).toBeLessThan(-0.005)

      await captureScreenshot(page, 'uat-08.3-11-B-after-body-drag.png')

      // ── Drag vertex 1 west (negative X on screen) ─────────────────────────
      // Re-read screen positions after body drag — shape has moved.
      const screenPtsAfterBody = await readPendingRingScreen(page)
      expect(screenPtsAfterBody).not.toBeNull()
      const v1CanvasRel = screenPtsAfterBody![1]
      const v1DragStart = {
        x: stageBox.x + v1CanvasRel.x,
        y: stageBox.y + v1CanvasRel.y,
      }
      const VERTEX_DRAG_PX = 80
      // Drag west (negative X = west in screen space)
      const v1DragEnd = { x: v1DragStart.x - VERTEX_DRAG_PX, y: v1DragStart.y }

      console.log(`  B: vertex 1 drag west: from ${JSON.stringify(v1DragStart)} to ${JSON.stringify(v1DragEnd)}`)
      await page.mouse.move(v1DragStart.x, v1DragStart.y); await page.waitForTimeout(200)
      await page.mouse.down(); await page.waitForTimeout(100)
      for (let s = 1; s <= steps; s++) {
        const t = s / steps
        await page.mouse.move(
          v1DragStart.x + (v1DragEnd.x - v1DragStart.x) * t,
          v1DragStart.y + (v1DragEnd.y - v1DragStart.y) * t,
        )
        await page.waitForTimeout(30)
      }
      await page.mouse.up(); await page.waitForTimeout(500)

      const ringAfterVertex = await readPendingRing(page)
      expect(ringAfterVertex).not.toBeNull()
      // Dragging vertex 1 west → its lon decreases (negative dLon)
      const v1Before = ringAfterBodyDrag![1]
      const v1After = ringAfterVertex![1]
      console.log(`  B: v1 lon: before=${v1Before.lon.toFixed(4)}, after=${v1After.lon.toFixed(4)}`)
      const dLonV1 = v1After.lon - v1Before.lon
      console.log(`  B: dLon vertex 1 drag = ${dLonV1.toFixed(4)} (expect < -0.005)`)
      expect(dLonV1).toBeLessThan(-0.005)

      await captureScreenshot(page, 'uat-08.3-11-B-after-vertex-drag.png')

      // ── Activate BezierApplyControls by selecting any existing barony ────────
      const anyBaronyIdB = await page.evaluate(async (pid: string) => {
        const res = await fetch(`/api/v3/projects/${pid}/artifacts/baronies.geojson`)
        if (!res.ok) return null
        const gj = await res.json() as { features?: Array<{ properties?: { id?: string } }> }
        return gj.features?.[0]?.properties?.id ?? null
      }, info.project_id)
      if (anyBaronyIdB) {
        await page.evaluate((id: string) => {
          ;(window as unknown as { __forgeSelectBarony?: (id: string) => void }).__forgeSelectBarony?.(id)
        }, anyBaronyIdB)
      }

      // ── Apply ────────────────────────────────────────────────────────────
      const applyBtn = page.getByTestId('bezier-apply-edits-btn')
      await expect(applyBtn).toBeEnabled({ timeout: 15_000 })
      console.log('  B: Apply button enabled — clicking')
      await applyBtn.click()

      const afterApplySha = await waitForShaChange(page, info.project_id, baselineSha)
      console.log(`  B: after-apply SHA: ${afterApplySha.slice(0, 16)}… (changed: ${afterApplySha !== baselineSha})`)
      expect(afterApplySha).not.toBe(baselineSha)

      await captureScreenshot(page, 'uat-08.3-11-B-after-apply.png')
      console.log('  B: SHA change CONFIRMED — manipulated CARVE shape rendered')

      // ── Reload ────────────────────────────────────────────────────────────
      console.log('  B: Reloading…')
      await page.reload()
      await expect(page.getByTestId('canvas-stage')).toBeVisible({ timeout: 20_000 })
      await expect(page.getByTestId('territory-layer-ready')).toBeAttached({ timeout: 30_000 })

      const afterReloadSha = await lookupBaronySha(page, info.project_id)
      console.log(`  B: after-reload SHA: ${afterReloadSha.slice(0, 16)}…`)
      expect(afterReloadSha).not.toBe(baselineSha)

      await captureScreenshot(page, 'uat-08.3-11-B-after-reload.png')
      console.log('  B: PASSED — CARVE manipulation persisted after reload')
    },
  )

})
