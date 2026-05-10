import { readFileSync } from 'node:fs'
import { test, expect } from '@playwright/test'

/**
 * SC-4 acceptance spec: clicking Cancelar mid-/render restores the canvas to
 * the prior visual and slider value within 500ms wall-clock (CI budget per
 * D-19; production target <50ms O(1) cache swap per D-13).
 *
 * Badge visibility contract (WorkspaceToolbar):
 *   rendering → badge HIDDEN, cancel button shown (showCancel = runState === 'rendering')
 *   generated → badge visible with "Mapa gerado"
 * So "render started" = badge element absent from DOM.
 *
 * Uses the same project fixture seeded by globalSetup.ts (Phase 03 UAT
 * infrastructure).
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

test.describe('Parameter Studio SC-4 cancel', () => {
  test('cancel restores prior cfg + canvas swap <500ms (D-19 CI budget)', async ({ page }) => {
    const info = loadProjectInfo()
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error' && !/Failed to load resource.*404/.test(msg.text())) {
        consoleErrors.push(msg.text())
      }
    })

    await page.goto(`/projects/${info.project_id}`)

    // Wait for workspace to settle with artifacts visible.
    await expect(page.getByTestId('canvas-stage')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('parameter-sidebar')).toBeVisible({ timeout: 10_000 })
    const badge = page.getByTestId('generate-status-badge')
    await expect(badge).toContainText(/Mapa gerado|Pronto/, { timeout: 30_000 })

    const canvasHandle = page.locator('[data-testid="canvas-stage"] canvas').first()
    await expect(canvasHandle).toBeVisible({ timeout: 10_000 })

    const sigmaInput = page.locator('input[type="number"][aria-label="Suavização (σ) value"]')

    // ── Warm-up render (untimed) ─────────────────────────────────────────────
    // Fires a full pipeline run at σ=3.1 so the cancel test runs against a
    // warm cache. Also ensures markRendered() fires once, setting up the
    // preRenderValues snapshot correctly for the cancel test below.
    await sigmaInput.fill('3.1')
    await sigmaInput.press('Enter')
    await waitForRenderCycle(page, { startTimeout: 5_000, completeTimeout: 120_000 })

    // Reset σ back to 3.0 baseline (the canonical default).
    await sigmaInput.fill('3')
    await sigmaInput.press('Enter')
    await waitForRenderCycle(page, { startTimeout: 5_000, completeTimeout: 30_000 })

    // ── Baseline capture ─────────────────────────────────────────────────────
    // Capture the baseline canvas pixel state and baseline σ value.
    const baseline = await canvasHandle.screenshot()
    const baselineSigma = await sigmaInput.inputValue()

    // ── Trigger render + cancel ──────────────────────────────────────────────
    // Trigger a render with σ=4.5. The 250ms debounce fires after Enter;
    // runStore transitions to 'rendering' (showCancel = runState === 'rendering').
    await sigmaInput.fill('4.5')
    await sigmaInput.press('Enter')

    // Wait for rendering to BEGIN.
    // Badge absent = cancel button visible = rendering started (badge hidden during rendering).
    await page.waitForFunction(
      () => {
        const el = document.querySelector('[data-testid="generate-status-badge"]')
        if (el === null) return true // badge hidden = rendering started
        return !/Mapa gerado|Pronto/.test(el.textContent ?? '')
      },
      { timeout: 2_000 },
    )

    // Wait for the cancel button to appear (runState === 'rendering').
    // UI-SPEC §State Machine: cancel-render-button only visible during 'rendering'.
    const cancelButton = page.getByTestId('cancel-render-button')
    await expect(cancelButton).toBeVisible({ timeout: 3_000 })

    // Click Cancelar. The /render/cancel endpoint sets stop_event, the SSE
    // emits stage_cancel, useRenderStream calls revertStage(), CanvasViewer
    // reads priorTokens.render as effectiveCacheVersion and re-fetches the
    // prior visual_condado.png. D-13: O(1) swap — no recompute on cancel.
    const start = Date.now()
    await cancelButton.click()

    // Wait for runStore to return to stable state (badge back to "Mapa gerado").
    // After cancel: useRenderStream sets cancelled=true + calls cancelRender()
    // which flips state back to 'generated' (prior artifacts visible).
    await page.waitForFunction(
      () => {
        const el = document.querySelector('[data-testid="generate-status-badge"]')
        return el !== null && /Mapa gerado|Pronto/.test(el.textContent ?? '')
      },
      { timeout: 5_000 },
    )
    const elapsed = Date.now() - start

    // SC-4 canvas assertion: prior artifacts restored.
    // Konva.clearCache() + re-fetch with priorTokens.render produces the same
    // visual_condado.png as before the σ change.
    const restored = await canvasHandle.screenshot()
    expect(
      Buffer.compare(baseline, restored),
      `Canvas not restored to baseline after cancel (elapsed ${elapsed}ms)`,
    ).toBe(0)

    // SC-4 slider assertion: σ input reverted to baseline value.
    // Use auto-retrying toHaveValue (not one-shot inputValue) so Playwright
    // waits for Zustand revertValues() to propagate to the DOM.
    await expect(sigmaInput, `σ input not restored: expected ${baselineSigma}`).toHaveValue(
      baselineSigma,
    )

    // SC-4 timing gate per D-19 (CI wall-clock budget 500ms from cancel click
    // to canvas-restored). Production target <50ms (D-13 O(1) cache swap) is
    // verified by the useCanvasArtifacts unit tests.
    expect(elapsed, `SC-4 cancel elapsed ${elapsed}ms exceeds 500ms CI budget`).toBeLessThan(500)

    // No console errors throughout the flow.
    expect(consoleErrors, `console errors: ${JSON.stringify(consoleErrors)}`).toEqual([])
  })
})
