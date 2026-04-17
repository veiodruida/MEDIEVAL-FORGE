import { test, expect } from '@playwright/test'
import { PNG } from 'pngjs'

// RESEARCH §Pitfall 2: Tailwind v4 + Radix transparency (GitHub #17137).
//
// NEGATIVE CONTROL (manual, not in CI):
//   Edit frontend/src/index.css to swap import order so '@import "tailwindcss"' comes
//   BEFORE '@import "@radix-ui/themes/styles.css"'. The visual-regression gate below
//   MUST fail (card becomes transparent, magenta Stage shows through).

test('Radix Card stays opaque over Konva Stage — visual regression + pixel sample', async ({ page }) => {
  await page.goto('/canvas-smoke')
  const card = page.getByTestId('smoke-card')
  await expect(card).toBeVisible()

  // PRIMARY gate: full-viewport screenshot diffed against committed baseline.
  // Baseline file: e2e/__baselines__/canvas-radix-overlay.png (committed).
  // Generate initially with: npm run test:e2e:update
  await expect(page).toHaveScreenshot('canvas-radix-overlay.png', { maxDiffPixelRatio: 0.02 })

  // SECONDARY gate: clip a screenshot of the card and read the center RGB from
  // the PNG pixel buffer — deterministic across browsers.
  const box = await card.boundingBox()
  if (!box) throw new Error('card bounding box unavailable')
  const buf = await page.screenshot({ clip: box, type: 'png' })
  const png = PNG.sync.read(buf)
  const cx = Math.floor(png.width / 2)
  const cy = Math.floor(png.height / 2)
  const idx = (png.width * cy + cx) << 2
  const [r, g, b, a] = [png.data[idx], png.data[idx + 1], png.data[idx + 2], png.data[idx + 3]]

  expect(a).toBeGreaterThan(200)                                   // opaque
  const isMagenta = r > 240 && g < 16 && b > 240                   // Stage fill bleed-through
  expect(isMagenta).toBe(false)

  // TERTIARY diagnostic: logged for debugging only — NOT a hard assertion.
  // Radix Themes v3 uses CSS layers + pseudo-elements for Card backgrounds.
  // getComputedStyle(card).backgroundColor returns "rgba(0, 0, 0, 0)" even when
  // the card visually renders with an opaque background (confirmed by screenshot).
  // The PRIMARY + SECONDARY gates above are the authoritative correctness checks.
  const computedBg = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="smoke-card"]') as HTMLElement
    return getComputedStyle(el).backgroundColor
  })
  // Log diagnostic value; test passes/fails on PRIMARY+SECONDARY gates only.
  console.log(`[diagnostic] card computed backgroundColor: ${computedBg}`)
  // Visual check: card's ::before or parent layering provides the background.
  // The screenshot-based gates above confirm opacity — no hard assertion here.
})
