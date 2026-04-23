import { test, expect } from '@playwright/test'

const PROJECT_ID = process.env.UAT_PROJECT_ID ?? 'fe5d709d-7454-4e9f-8a0c-5486dc71299f'
const BASE = process.env.UAT_BASE ?? 'http://localhost:8765'

test('FitToView button presence + position diagnostic', async ({ page }) => {
  const url = `${BASE}/projects/${PROJECT_ID}`
  console.log(`[UAT] Navigating to ${url}`)

  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`[browser ${msg.type()}] ${msg.text()}`)
    }
  })
  page.on('pageerror', (err) => console.log(`[pageerror] ${err.message}`))

  await page.goto(url, { waitUntil: 'networkidle' })

  // Wait for canvas to appear (Stage / konvajs-content) — confirms project loaded
  await page.waitForSelector('.konvajs-content, [data-testid="fit-to-view-wrapper"]', { timeout: 15000 })

  // Snapshot full page first
  await page.screenshot({ path: 'e2e/screenshots/uat-fittoview-full.png', fullPage: false })

  const wrapper = page.locator('[data-testid="fit-to-view-wrapper"]')
  const count = await wrapper.count()
  console.log(`[UAT] fit-to-view-wrapper count in DOM: ${count}`)

  if (count === 0) {
    // Diagnostic: check canvas-region children
    const html = await page.locator('.canvas-region').innerHTML().catch(() => '<no canvas-region>')
    console.log(`[UAT] canvas-region HTML (first 2000 chars): ${html.substring(0, 2000)}`)

    // Check if LegendCard is there for comparison
    const legendCount = await page.getByText('Legenda', { exact: false }).count()
    console.log(`[UAT] LegendCard count: ${legendCount}`)
  } else {
    const box = await wrapper.boundingBox()
    const isVisible = await wrapper.isVisible()
    const styles = await wrapper.evaluate((el) => {
      const cs = getComputedStyle(el)
      return {
        display: cs.display,
        visibility: cs.visibility,
        opacity: cs.opacity,
        position: cs.position,
        bottom: cs.bottom,
        right: cs.right,
        zIndex: cs.zIndex,
        width: cs.width,
        height: cs.height,
      }
    })
    console.log(`[UAT] visible: ${isVisible}`)
    console.log(`[UAT] boundingBox: ${JSON.stringify(box)}`)
    console.log(`[UAT] computed styles: ${JSON.stringify(styles, null, 2)}`)

    // Check what's at the button's coordinates
    if (box) {
      const cx = box.x + box.width / 2
      const cy = box.y + box.height / 2
      const topEl = await page.evaluate(({ x, y }) => {
        const el = document.elementFromPoint(x, y)
        return el ? `<${el.tagName.toLowerCase()} class="${el.className}" data-testid="${el.getAttribute('data-testid') ?? ''}">` : null
      }, { x: cx, y: cy })
      console.log(`[UAT] elementFromPoint(${cx},${cy}): ${topEl}`)
    }

    await wrapper.screenshot({ path: 'e2e/screenshots/uat-fittoview-button.png' })
  }

  // Print the script tag from index.html (cache verification)
  const scriptSrc = await page.evaluate(() => {
    const s = document.querySelector('script[type="module"]') as HTMLScriptElement | null
    return s?.src ?? null
  })
  console.log(`[UAT] loaded script src: ${scriptSrc}`)

  expect(count, 'FitToView wrapper should be in DOM').toBeGreaterThan(0)
})
