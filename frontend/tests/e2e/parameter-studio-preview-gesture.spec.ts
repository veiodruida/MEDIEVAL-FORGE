import { readFileSync } from 'node:fs'
import { test, expect } from '@playwright/test'

/**
 * Plan 04.1-05 SC-2 (D-02) acceptance spec: AFTER a slider-driven render
 * settles, holding spacebar swaps the canvas to the previousCacheVersion and
 * shows the "Anterior" PT-BR badge; releasing reverts to the current
 * cacheVersion.
 *
 * Contract this spec relies on (codified by Plan 04.1-03 Task 2):
 *   - CanvasViewer.tsx tracks previousCacheVersion via useRef+useState and
 *     promotes the prior cacheVersion prop on every transition.
 *   - effectiveCacheVersion precedence: previewPrior && previousCacheVersion
 *     → previousCacheVersion ; else priorTokens.render !== undefined →
 *     priorTokens.render ; else cacheVersion.
 *   - useCanvasArtifacts uses ?v=<cacheVersion> query-string cache busting
 *     so v1 and v2 rasters coexist in the browser HTTP cache.
 *
 * Setup: σ default is 3.0 per RegionConfig. Step 1 uses 3.2 (NOT 3.0) so the
 * first fill triggers a real prop transition. Step 2 uses 4.5 so the v1 → v2
 * transition promotes 3.2's cacheVersion to previousCacheVersion.
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

test.describe('Parameter Studio SC-2 preview gesture (D-02)', () => {
  test('after settled new render, hold spacebar shows previous raster + "Anterior" badge; release restores current', async ({ page }) => {
    const info = loadProjectInfo()
    await page.goto(`/projects/${info.project_id}`)

    await expect(page.getByTestId('canvas-stage')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('parameter-sidebar')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByTestId('generate-status-badge')).toContainText(
      /Mapa gerado|Pronto/,
      { timeout: 30_000 },
    )

    const sigmaInput = page.locator('input[type="number"][aria-label="Suavização (σ) value"]')
    const canvas = page.locator('[data-testid="canvas-stage"] canvas').first()

    // Step 1: Establish the FIRST settled state at σ=3.2 (RegionConfig default
    // is 3.0, so 3.2 forces a prop transition + new cacheVersion = v1).
    await sigmaInput.fill('3.2')
    await sigmaInput.press('Enter')
    await waitForRenderCycle(page, { startTimeout: 5_000, completeTimeout: 120_000 })

    // Allow the v1 raster fetch (`?v=v1`) to settle into the HTTP cache.
    await page.waitForTimeout(300)

    // Step 2: Trigger the SECOND settled state at σ=4.5 (cacheVersion = v2).
    // The prop transition v1 → v2 inside CanvasViewer promotes v1 to
    // `previousCacheVersion`. After this completes, the spacebar gesture is
    // enabled.
    await sigmaInput.fill('4.5')
    await sigmaInput.press('Enter')
    await waitForRenderCycle(page, { startTimeout: 5_000, completeTimeout: 60_000 })

    // Step 3: Capture the current settled state (canvas shows v2 raster).
    await page.waitForTimeout(300) // let Konva batchDraw settle
    const currentSnapshot = await canvas.screenshot()

    // The spacebar handler in CanvasViewer skips when e.target is an INPUT,
    // TEXTAREA, or contenteditable element (guard against typing-in-slider
    // intercept). After Enter the σ input may still hold focus — blur it
    // before pressing Space so the keydown lands on document.body.
    await sigmaInput.blur()
    await page.locator('body').click({ position: { x: 1, y: 1 }, force: true })
    await page.waitForTimeout(50)

    // Step 4: Press-and-hold spacebar. The Anterior badge must appear and
    // the canvas must swap to the v1 raster (previousCacheVersion).
    await page.keyboard.down('Space')
    await expect(page.getByTestId('preview-prior-badge')).toBeVisible({ timeout: 1_000 })
    await expect(page.getByTestId('preview-prior-badge')).toHaveText('Anterior')

    // Allow the prior raster to render from the warm HTTP cache.
    await page.waitForTimeout(500)
    const heldSnapshot = await canvas.screenshot()

    // Step 5: The canvas pixels MUST differ from the current state (σ=3.2 vs
    // σ=4.5 produces visibly different smoothing).
    expect(
      Buffer.compare(currentSnapshot, heldSnapshot),
      'Canvas did not swap to previous raster while spacebar held — D-02 gesture not wired (Plan 04.1-03 Task 2 regression)',
    ).not.toBe(0)

    // Step 6: Release spacebar. Badge gone, canvas restored to current (v2).
    await page.keyboard.up('Space')
    await expect(page.getByTestId('preview-prior-badge')).toHaveCount(0, { timeout: 1_000 })
    await page.waitForTimeout(500)
    const releasedSnapshot = await canvas.screenshot()

    // Step 7: After release, canvas matches the v2 snapshot (effective
    // cacheVersion back to cacheVersion, not priorTokens.render).
    expect(
      Buffer.compare(currentSnapshot, releasedSnapshot),
      'Canvas did not restore current raster after spacebar release',
    ).toBe(0)
  })
})
