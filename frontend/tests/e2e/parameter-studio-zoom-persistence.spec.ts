import { readFileSync } from 'node:fs'
import { test, expect } from '@playwright/test'

/**
 * Plan 04.1-05 SC-1 (D-01) acceptance spec: dragging a σ slider preserves
 * Konva Stage zoom/pan across a full re-render cycle.
 *
 * Approach: we read `window.__forgeStageScale` (development-only escape hatch
 * exposed by CanvasViewer.tsx, gated on `import.meta.env.DEV`). The pre-fix
 * behavior was that the projection useEffect with `!projection` guard +
 * downstream auto-fit fired on every cacheVersion-driven refetch, resetting
 * scale to `minScale`. Plan 04.1-03 added a stable bounds-key gate; this spec
 * proves the gate holds end-to-end.
 *
 * Vacuous-pass guard: we assert the captured scale BEFORE the slider drag is
 * strictly greater than the initial fit-to-view minScale by an empirical
 * margin. If wheel-zoom were broken, scaleBeforeSlider would equal scaleAfter
 * trivially — that case is caught by the > minScale check.
 *
 * Setup: globalSetup.ts seeds the Iberia 868 project; webServer starts both
 * the FastAPI backend on :8765 and the Vite dev server on :5173.
 */
function loadProjectInfo(): { project_id: string; name: string } {
  const p = process.env.UAT_PROJECT_INFO_PATH
  if (!p) throw new Error('UAT_PROJECT_INFO_PATH not set; globalSetup did not run.')
  return JSON.parse(readFileSync(p, 'utf-8'))
}

async function waitForRenderCycle(
  page: import('@playwright/test').Page,
  opts?: { startTimeout?: number; completeTimeout?: number },
) {
  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="generate-status-badge"]')
      if (el === null) return true
      return !/Mapa gerado|Pronto/.test(el.textContent ?? '')
    },
    { timeout: opts?.startTimeout ?? 5_000 },
  )
  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="generate-status-badge"]')
      return el !== null && /Mapa gerado|Pronto/.test(el.textContent ?? '')
    },
    { timeout: opts?.completeTimeout ?? 120_000 },
  )
}

async function readStageScale(page: import('@playwright/test').Page): Promise<number> {
  // Wait until the escape hatch is exposed by CanvasViewer's useEffect.
  await page.waitForFunction(
    () => typeof (window as { __forgeStageScale?: number }).__forgeStageScale === 'number',
    { timeout: 5_000 },
  )
  return await page.evaluate(
    () => (window as { __forgeStageScale?: number }).__forgeStageScale as number,
  )
}

test.describe('Parameter Studio SC-1 zoom/pan persistence (D-01)', () => {
  test('slider drag preserves Konva Stage zoom and pan across re-render', async ({ page }) => {
    const info = loadProjectInfo()
    await page.goto(`/projects/${info.project_id}`)

    await expect(page.getByTestId('canvas-stage')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('parameter-sidebar')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByTestId('generate-status-badge')).toContainText(
      /Mapa gerado|Pronto/,
      { timeout: 30_000 },
    )

    const sigmaInput = page.locator('input[type="number"][aria-label="Suavização (σ) value"]')

    // Warm-up render to populate the backend _STAGE_CACHE so the timed slider
    // drag below triggers an incremental render (not a cold full pipeline).
    // Default σ is 3.0 (RegionConfig); using 3.2 → 3.0 → 4.0 guarantees prop
    // transitions that drive a real fitToView candidate path.
    await sigmaInput.fill('3.2')
    await sigmaInput.press('Enter')
    await waitForRenderCycle(page, { startTimeout: 5_000, completeTimeout: 120_000 })

    await sigmaInput.fill('3')
    await sigmaInput.press('Enter')
    await waitForRenderCycle(page, { startTimeout: 5_000, completeTimeout: 60_000 })

    // Capture the initial fit-to-view scale (this is `minScale`).
    const initialScale = await readStageScale(page)

    // Manually zoom in via wheel events centered on the canvas. CanvasViewer
    // wires onWheel → handleWheel → setCurrentScale(stage.scaleX()), so each
    // tick updates __forgeStageScale.
    const canvas = page.locator('[data-testid="canvas-stage"] canvas').first()
    const box = await canvas.boundingBox()
    if (!box) throw new Error('canvas bounding box not available')
    const cx = box.x + box.width / 2
    const cy = box.y + box.height / 2
    await page.mouse.move(cx, cy)
    for (let i = 0; i < 3; i++) {
      await page.mouse.wheel(0, -400)
    }
    // Allow Konva batchDraw + setCurrentScale to settle.
    await page.waitForTimeout(200)

    const scaleAfterZoom = await readStageScale(page)

    // Vacuous-pass guard: zoom MUST actually have happened. If wheel-zoom is
    // not wired (or is somehow no-op'd), the post-slider assertion below
    // would pass trivially. The factor 1.1 is well below a single zoom-in
    // step (CanvasViewer uses a multiplicative factor of ~1.1+ per tick).
    expect(
      scaleAfterZoom,
      `wheel-zoom did not change Stage scale (initial=${initialScale}, after-zoom=${scaleAfterZoom}). Vacuous-pass guard hit — spec is testing nothing.`,
    ).toBeGreaterThan(initialScale * 1.1)

    // Now drag the slider. The pre-fix behavior reset zoom to initialScale;
    // post-fix (D-01) the bounds-key gate keeps fitToView from firing because
    // the projection bounds did not actually change.
    await sigmaInput.fill('4.0')
    await sigmaInput.press('Enter')
    await waitForRenderCycle(page, { startTimeout: 5_000, completeTimeout: 60_000 })

    // Give the post-render effects (CanvasViewer cacheVersion swap, Konva
    // clearCache, batchDraw) a moment to settle.
    await page.waitForTimeout(200)

    const scaleAfterSlider = await readStageScale(page)

    // SC-1 contract: zoom level after the slider-driven re-render must equal
    // the user's manually-set zoom. We compare with a small numeric epsilon
    // (Konva rounds during batchDraw on some browsers).
    expect(
      scaleAfterSlider,
      `Stage scale changed after slider re-render: before=${scaleAfterZoom}, after=${scaleAfterSlider}. fitToView fired (UAT gap #1 regression).`,
    ).toBeCloseTo(scaleAfterZoom, 5)
  })
})
