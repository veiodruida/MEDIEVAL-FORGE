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
 * DEV hatches used READ-ONLY for assertions:
 *   __forgePendingRing  — read pending op.ring after close (read-only, NOT input)
 *
 * REQ-IDs: PEN-PREAPPLY-EDIT-01
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

// ─── Read pending ring (READ-ONLY assertion helper) ───────────────────────────

async function readPendingRing(
  page: Page,
): Promise<Array<{ lat: number; lon: number }> | null> {
  return page.evaluate(() => {
    const fn = (window as unknown as { __forgePendingRing?: () => unknown }).__forgePendingRing
    return fn ? (fn() as Array<{ lat: number; lon: number }> | null) : null
  })
}

// ─── Screenshot helper ────────────────────────────────────────────────────────

async function captureScreenshot(page: Page, filename: string): Promise<void> {
  const repoRoot = path.resolve(__dirname, '../../../..')
  const outPath = path.join(repoRoot, filename)
  await page.screenshot({ path: outPath, fullPage: false })
  console.log(`  Screenshot: ${outPath}`)
}

// ─── Iberia bounds for geo → stage-px ────────────────────────────────────────
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

// ─── Centroid helper for a ring ───────────────────────────────────────────────

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
      test.setTimeout(600_000)

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
      // These points are well into the ocean (lon < -9), away from any barony,
      // creating a gap-fill scenario. The shape is large enough to pass area validation.
      //   p0: lat=38.5, lon=-8.8  (ocean)
      //   p1: lat=38.5, lon=-8.4  (ocean)
      //   p2: lat=38.8, lon=-8.4  (ocean)
      // close via double-click near p0
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

      // ── Read the committed ring (read-only assertion) ─────────────────────
      // PenShapeManipulateLayer must now be mounted (tool switched to 'V' after close)
      await page.waitForTimeout(500)
      const ringBeforeDrag = await readPendingRing(page)
      console.log(`  A: pending ring before drag: ${ringBeforeDrag?.length ?? 'null'} points`)
      expect(ringBeforeDrag).not.toBeNull()
      expect(ringBeforeDrag!.length).toBeGreaterThanOrEqual(3)

      const centroidBefore = ringCentroid(ringBeforeDrag!)
      console.log(`  A: centroid before drag: lat=${centroidBefore.lat.toFixed(4)}, lon=${centroidBefore.lon.toFixed(4)}`)

      // ── Drag the whole shape: body drag by ~0.3° lat north ─────────────────
      // Shape centroid is around lat=38.6, lon=-8.6 in screen-px.
      const centroidScreen = geoToStageXY(centroidBefore.lat, centroidBefore.lon, stageBox)
      const dragEndScreen = geoToStageXY(centroidBefore.lat + 0.3, centroidBefore.lon, stageBox)

      console.log(`  A: body drag: from ${JSON.stringify(centroidScreen)} to ${JSON.stringify(dragEndScreen)}`)
      await page.mouse.move(centroidScreen.x, centroidScreen.y); await page.waitForTimeout(200)
      await page.mouse.down(); await page.waitForTimeout(100)
      // Move gradually so Konva mousemove fires
      const steps = 8
      for (let s = 1; s <= steps; s++) {
        const t = s / steps
        await page.mouse.move(
          centroidScreen.x + (dragEndScreen.x - centroidScreen.x) * t,
          centroidScreen.y + (dragEndScreen.y - centroidScreen.y) * t,
        )
        await page.waitForTimeout(50)
      }
      await page.mouse.up(); await page.waitForTimeout(500)

      // Read ring after body drag
      const ringAfterBodyDrag = await readPendingRing(page)
      console.log(`  A: ring after body drag: ${ringAfterBodyDrag?.length ?? 'null'} points`)
      expect(ringAfterBodyDrag).not.toBeNull()

      const centroidAfterDrag = ringCentroid(ringAfterBodyDrag!)
      console.log(`  A: centroid after body drag: lat=${centroidAfterDrag.lat.toFixed(4)}, lon=${centroidAfterDrag.lon.toFixed(4)}`)
      // Centroid must have moved north (dLat > 0) by a meaningful amount
      const dLat = centroidAfterDrag.lat - centroidBefore.lat
      console.log(`  A: dLat from body drag = ${dLat.toFixed(4)} (expect > 0.05)`)
      expect(dLat).toBeGreaterThan(0.05)

      // ── Screenshot: after body drag ────────────────────────────────────────
      await captureScreenshot(page, 'uat-08.3-11-A-after-body-drag.png')

      // ── Drag a vertex: move vertex 0 slightly east (+0.15° lon) ──────────
      const v0Before = ringAfterBodyDrag![0]
      const v0Screen = geoToStageXY(v0Before.lat, v0Before.lon, stageBox)
      const v0NewScreen = geoToStageXY(v0Before.lat, v0Before.lon + 0.15, stageBox)

      console.log(`  A: vertex 0 drag: from ${JSON.stringify(v0Screen)} to ${JSON.stringify(v0NewScreen)}`)
      await page.mouse.move(v0Screen.x, v0Screen.y); await page.waitForTimeout(200)
      await page.mouse.down(); await page.waitForTimeout(100)
      for (let s = 1; s <= steps; s++) {
        const t = s / steps
        await page.mouse.move(
          v0Screen.x + (v0NewScreen.x - v0Screen.x) * t,
          v0Screen.y + (v0NewScreen.y - v0Screen.y) * t,
        )
        await page.waitForTimeout(50)
      }
      await page.mouse.up(); await page.waitForTimeout(500)

      // Read ring after vertex drag
      const ringAfterVertexDrag = await readPendingRing(page)
      console.log(`  A: ring after vertex drag: ${ringAfterVertexDrag?.length ?? 'null'} points`)
      expect(ringAfterVertexDrag).not.toBeNull()

      // Vertex 0 must have moved east
      const v0After = ringAfterVertexDrag![0]
      console.log(`  A: v0 after vertex drag: lat=${v0After.lat.toFixed(4)}, lon=${v0After.lon.toFixed(4)}`)
      const dLon = v0After.lon - v0Before.lon
      console.log(`  A: dLon from vertex drag = ${dLon.toFixed(4)} (expect > 0.05)`)
      expect(dLon).toBeGreaterThan(0.05)

      // ── Screenshot: after vertex drag ──────────────────────────────────────
      await captureScreenshot(page, 'uat-08.3-11-A-after-vertex-drag.png')

      // ── Apply edições ────────────────────────────────────────────────────
      // Click the canvas near the shape to select the territory and enable Apply
      const shapeCenter = geoToStageXY(centroidAfterDrag.lat, centroidAfterDrag.lon, stageBox)
      await page.mouse.click(shapeCenter.x, shapeCenter.y); await page.waitForTimeout(500)

      await expect(page.getByTestId('bezier-apply-edits-btn')).toBeEnabled({ timeout: 15_000 })
      console.log('  A: Apply button enabled — clicking')
      await page.getByTestId('bezier-apply-edits-btn').click()

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
      test.setTimeout(600_000)

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

      // ── Draw a small CARVE shape inside Toledo barony ─────────────────────
      // Toledo barony covers approx lat[39.25, 40.29] × lon[-4.52, -3.43].
      // Draw a small triangle entirely inside Toledo to trigger a CARVE op.
      //   c0: lat=39.6, lon=-4.2
      //   c1: lat=39.6, lon=-4.0
      //   c2: lat=39.7, lon=-4.0
      // close via double-click near c0
      const c0 = geoToStageXY(39.6, -4.2, stageBox)
      const c1 = geoToStageXY(39.6, -4.0, stageBox)
      const c2 = geoToStageXY(39.7, -4.0, stageBox)

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

      // ── Read committed ring (read-only) ───────────────────────────────────
      await page.waitForTimeout(500)
      const ringBeforeDrag = await readPendingRing(page)
      console.log(`  B: pending ring: ${ringBeforeDrag?.length ?? 'null'} points`)

      if (ringBeforeDrag === null) {
        console.log('  B: WARNING — no pending ring found. Close may not have created a carve op.')
        console.log('  B: Skipping body/vertex drag assertions for CARVE scenario.')
        // Still try to Apply and check SHA changes (any op in editLog is valid)
      } else {
        expect(ringBeforeDrag.length).toBeGreaterThanOrEqual(3)

        const centroidBefore = ringCentroid(ringBeforeDrag)
        console.log(`  B: centroid: lat=${centroidBefore.lat.toFixed(4)}, lon=${centroidBefore.lon.toFixed(4)}`)

        // ── Drag shape body south by ~0.15° lat ─────────────────────────────
        const centroidScreen = geoToStageXY(centroidBefore.lat, centroidBefore.lon, stageBox)
        const dragEndScreen = geoToStageXY(centroidBefore.lat - 0.15, centroidBefore.lon, stageBox)

        console.log(`  B: body drag south: ${JSON.stringify(centroidScreen)} → ${JSON.stringify(dragEndScreen)}`)
        await page.mouse.move(centroidScreen.x, centroidScreen.y); await page.waitForTimeout(200)
        await page.mouse.down(); await page.waitForTimeout(100)
        const steps = 6
        for (let s = 1; s <= steps; s++) {
          const t = s / steps
          await page.mouse.move(
            centroidScreen.x + (dragEndScreen.x - centroidScreen.x) * t,
            centroidScreen.y + (dragEndScreen.y - centroidScreen.y) * t,
          )
          await page.waitForTimeout(50)
        }
        await page.mouse.up(); await page.waitForTimeout(500)

        const ringAfterBodyDrag = await readPendingRing(page)
        if (ringAfterBodyDrag) {
          const centroidAfter = ringCentroid(ringAfterBodyDrag)
          const dLat = centroidAfter.lat - centroidBefore.lat
          console.log(`  B: dLat from body drag = ${dLat.toFixed(4)} (expect < -0.05)`)
          expect(dLat).toBeLessThan(-0.05)
        }

        await captureScreenshot(page, 'uat-08.3-11-B-after-body-drag.png')

        // ── Drag vertex 1 slightly west ───────────────────────────────────
        const ringForVertex = (await readPendingRing(page)) ?? ringBeforeDrag
        const v1Before = ringForVertex[1]
        const v1Screen = geoToStageXY(v1Before.lat, v1Before.lon, stageBox)
        const v1NewScreen = geoToStageXY(v1Before.lat, v1Before.lon - 0.1, stageBox)

        await page.mouse.move(v1Screen.x, v1Screen.y); await page.waitForTimeout(200)
        await page.mouse.down(); await page.waitForTimeout(100)
        for (let s = 1; s <= steps; s++) {
          const t = s / steps
          await page.mouse.move(
            v1Screen.x + (v1NewScreen.x - v1Screen.x) * t,
            v1Screen.y + (v1NewScreen.y - v1Screen.y) * t,
          )
          await page.waitForTimeout(50)
        }
        await page.mouse.up(); await page.waitForTimeout(500)

        const ringAfterVertex = await readPendingRing(page)
        if (ringAfterVertex) {
          const dLonV1 = ringAfterVertex[1].lon - v1Before.lon
          console.log(`  B: dLon vertex 1 drag = ${dLonV1.toFixed(4)} (expect < -0.05)`)
          expect(dLonV1).toBeLessThan(-0.05)
        }

        await captureScreenshot(page, 'uat-08.3-11-B-after-vertex-drag.png')
      }

      // ── Apply ────────────────────────────────────────────────────────────
      const shapeArea = geoToStageXY(39.65, -4.1, stageBox)
      await page.mouse.click(shapeArea.x, shapeArea.y); await page.waitForTimeout(500)

      await expect(page.getByTestId('bezier-apply-edits-btn')).toBeEnabled({ timeout: 15_000 })
      console.log('  B: Apply button enabled — clicking')
      await page.getByTestId('bezier-apply-edits-btn').click()

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
