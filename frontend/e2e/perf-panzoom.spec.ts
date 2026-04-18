import { test, expect } from '@playwright/test'

/**
 * A5 perf probe — measures pan/zoom FPS over a 2s stress loop.
 * Skipped unless MF_PERF_FIXTURE_PROJECT_ID env var points at a generated project.
 * This is a non-requirement perf sanity check, not a blocking gate.
 */
const fixtureId = process.env.MF_PERF_FIXTURE_PROJECT_ID

test.describe('pan/zoom perf probe', () => {
  test.skip(!fixtureId, 'MF_PERF_FIXTURE_PROJECT_ID not set — skipping perf probe')

  test('sustains > 30 FPS under sustained wheel zoom', async ({ page }) => {
    await page.goto(`/projects/${fixtureId}`)
    // Wait for canvas to mount
    await page.waitForSelector('canvas')

    const fps = await page.evaluate(async () => {
      let frames = 0
      let stop = false
      const start = performance.now()
      const loop = () => {
        frames++
        if (!stop) requestAnimationFrame(loop)
      }
      requestAnimationFrame(loop)

      // Dispatch 40 wheel events over ~2s
      const canvas = document.querySelector('canvas')!
      const rect = canvas.getBoundingClientRect()
      for (let i = 0; i < 40; i++) {
        canvas.dispatchEvent(
          new WheelEvent('wheel', {
            deltaY: i % 2 === 0 ? -120 : 120,
            clientX: rect.left + rect.width / 2,
            clientY: rect.top + rect.height / 2,
            bubbles: true,
            cancelable: true,
          }),
        )
        await new Promise((r) => setTimeout(r, 50))
      }
      stop = true
      const elapsed = (performance.now() - start) / 1000
      return frames / elapsed
    })

    expect(fps).toBeGreaterThan(30)
  })
})
