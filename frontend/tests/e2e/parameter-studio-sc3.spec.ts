import { readFileSync } from 'node:fs'
import { test, expect } from '@playwright/test'

/**
 * SC-3 acceptance spec: σ slider 3.0 → 4.5 produces a visible canvas pixel
 * diff after the incremental re-render completes.
 *
 * Timing note (D-19 / T-04-06-01): The 500ms wall-clock budget covers
 * 250ms debounce + backend incremental smooth-stage recompute + SSE drain +
 * Konva clearCache. On warm cache, backend recompute takes ~200ms. We wait
 * for the render to complete (badge back to "Mapa gerado"), then assert:
 *   (a) canvas pixels differ from the pre-change snapshot
 *   (b) elapsed from Enter → completion < 500ms
 *
 * Uses the same project fixture seeded by globalSetup.ts (Phase 03 UAT
 * infrastructure). The project must already have artifacts for CanvasViewer
 * to hydrate.
 *
 * Badge visibility contract (WorkspaceToolbar):
 *   rendering → badge HIDDEN, cancel button shown (showCancel = runState === 'rendering')
 *   generated → badge visible with "Mapa gerado"
 * So "render started" = badge element absent from DOM.
 */
function loadProjectInfo(): { project_id: string; name: string } {
  const p = process.env.UAT_PROJECT_INFO_PATH
  if (!p) {
    throw new Error(
      'UAT_PROJECT_INFO_PATH not set; globalSetup did not run. Launch via `npx playwright test`.',
    )
  }
  return JSON.parse(readFileSync(p, 'utf-8'))
}

/** Wait for badge to disappear (rendering started) then reappear (rendering done). */
async function waitForRenderCycle(
  page: import('@playwright/test').Page,
  opts?: { startTimeout?: number; completeTimeout?: number },
) {
  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="generate-status-badge"]')
      if (el === null) return true // badge hidden = rendering active
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

test.describe('Parameter Studio SC-3 timing', () => {
  test('sigma 3.0 to 4.5 produces visible canvas pixel diff in <500ms', async ({ page }) => {
    const info = loadProjectInfo()
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error' && !/Failed to load resource.*404/.test(msg.text())) {
        consoleErrors.push(msg.text())
      }
    })

    await page.goto(`/projects/${info.project_id}`)

    // Wait for canvas and parameter sidebar to be ready.
    await expect(page.getByTestId('canvas-stage')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('parameter-sidebar')).toBeVisible({ timeout: 10_000 })

    // Wait for the initial artifact render to settle (badge shows "Mapa gerado").
    const badge = page.getByTestId('generate-status-badge')
    await expect(badge).toContainText(/Mapa gerado|Pronto/, { timeout: 30_000 })

    const canvasHandle = page.locator('[data-testid="canvas-stage"] canvas').first()
    await expect(canvasHandle).toBeVisible({ timeout: 10_000 })

    // SliderCard aria-label = `${label} value` = "Suavização (σ) value"
    const sigmaInput = page.locator('input[type="number"][aria-label="Suavização (σ) value"]')

    // ── Warm-up render (untimed) ─────────────────────────────────────────────
    // Populates backend _STAGE_CACHE so the timed run only recomputes smooth.
    // σ=3.1 produces a full pipeline run; on completion the smooth-stage cache
    // entry exists and the timed σ=4.5 run only redoes smooth+downstream.
    await sigmaInput.fill('3.1')
    await sigmaInput.press('Enter')
    await waitForRenderCycle(page, { startTimeout: 5_000, completeTimeout: 120_000 })

    // Reset σ back to 3.0 baseline (the canonical default).
    await sigmaInput.fill('3')
    await sigmaInput.press('Enter')
    await waitForRenderCycle(page, { startTimeout: 5_000, completeTimeout: 30_000 })

    // Capture the baseline canvas snapshot before the parameter change.
    const before = await canvasHandle.screenshot()

    // ── Timed measurement: 3.0 → 4.5 ────────────────────────────────────────
    await sigmaInput.fill('4.5')

    // Record wall-clock start at Enter press.
    // Timer covers: 250ms debounce + backend incremental recompute + SSE drain + canvas swap.
    const start = Date.now()
    await sigmaInput.press('Enter')

    // Step 1: Wait for rendering to BEGIN.
    await page.waitForFunction(
      () => {
        const el = document.querySelector('[data-testid="generate-status-badge"]')
        // Badge absent = cancel button visible = rendering started.
        // Badge present with non-stable text = also rendering (e.g., "Gerando: smooth").
        if (el === null) return true
        return !/Mapa gerado|Pronto/.test(el.textContent ?? '')
      },
      { timeout: 2_000 }, // debounce is 250ms; rendering should start within 1s
    )

    // Step 2: Wait for rendering to COMPLETE (badge returns to "Mapa gerado").
    // Safety upper bound: 10s for full pipeline; assertion below is the real gate.
    await page.waitForFunction(
      () => {
        const el = document.querySelector('[data-testid="generate-status-badge"]')
        return el !== null && /Mapa gerado|Pronto/.test(el.textContent ?? '')
      },
      { timeout: 10_000 },
    )
    const elapsed = Date.now() - start

    // Capture the post-render snapshot.
    const after = await canvasHandle.screenshot()

    // SC-3: pixels must differ (σ change reformats smooth stage output).
    expect(
      Buffer.compare(before, after),
      `Canvas pixels unchanged after σ 3.0→4.5 (elapsed ${elapsed}ms)`,
    ).not.toBe(0)

    // SC-3 timing gate: full roundtrip from Enter to canvas-updated < 500ms.
    // D-19 CI wall-clock budget. The production target is 250ms debounce +
    // ~200ms warm-cache backend compute + ~50ms canvas swap.
    expect(elapsed, `SC-3 elapsed ${elapsed}ms exceeds 500ms budget`).toBeLessThan(500)

    // No console errors throughout the flow.
    expect(consoleErrors, `console errors: ${JSON.stringify(consoleErrors)}`).toEqual([])
  })
})
