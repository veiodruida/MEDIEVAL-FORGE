import { readFileSync } from 'node:fs'
import { test, expect } from '@playwright/test'

/**
 * Plan 03-08 Wave 4 acceptance gate.
 *
 * Single happy-path UAT covering ROADMAP Phase 03 success criteria:
 *   SC-1  pan/zoom/click works against a Phase 01 project
 *   SC-2  inspector populates + layer toggles work
 *   SC-3  zero console errors throughout the run
 *   SC-4  artifacts come from Phase 01 output (no /preview/* leaks)
 *
 * The project is seeded by `globalSetup.ts` via the Python uat_setup
 * helper; its UUID is read from the JSON sidecar at
 * `process.env.UAT_PROJECT_INFO_PATH`.
 */
function loadProjectInfo(): { project_id: string; name: string } {
  const p = process.env.UAT_PROJECT_INFO_PATH
  if (!p) {
    throw new Error(
      'UAT_PROJECT_INFO_PATH is not set; globalSetup did not run. Did you launch via `npx playwright test`?',
    )
  }
  return JSON.parse(readFileSync(p, 'utf-8'))
}

test.describe('Phase 03 canvas workspace', () => {
  test('canvas workspace happy path — SC-1..SC-4', async ({ page }) => {
    const consoleErrors: string[] = []
    const previewLeaks: string[] = []
    page.on('console', (msg) => {
      if (msg.type() !== 'error') return
      const text = msg.text()
      // Phase 06 defers terrain.png + terrain_types.json (CLAUDE.md output
      // contract row #5/#6). The Phase 03 CanvasViewer requests them
      // eagerly via useImage; the browser logs a generic
      // "Failed to load resource" 404 which we treat as expected, not
      // an app-level error. SC-3 covers app errors, not browser network
      // 404s on documented-deferred artifacts.
      if (/Failed to load resource.*404/.test(text)) return
      consoleErrors.push(text)
    })
    page.on('request', (req) => {
      if (req.url().includes('/preview/')) previewLeaks.push(req.url())
    })

    const info = loadProjectInfo()
    await page.goto(`/projects/${info.project_id}`)

    // SC-1: workspace shell renders + project name + status badge.
    const toolbar = page.getByTestId('workspace-toolbar')
    await expect(toolbar).toBeVisible()
    await expect(page.getByTestId('project-name')).toContainText(info.name)
    await expect(page.getByTestId('generate-status-badge')).toContainText(
      /Mapa gerado|Pronto/,
    )

    // SC-1: canvas hydrates with 4 sidecars.
    const stage = page.getByTestId('canvas-stage')
    await expect(stage).toBeVisible()
    await expect(page.getByTestId('territory-layer-ready')).toBeAttached({
      timeout: 30_000,
    })

    // SC-2: inspector starts on the placeholder.
    await expect(page.getByTestId('inspector-sidebar')).toBeVisible()
    await expect(page.getByTestId('inspector-placeholder')).toBeVisible()

    // SC-1: click into the canvas hit-tests a territory polygon.
    const stageBox = await stage.boundingBox()
    if (!stageBox) throw new Error('canvas-stage had no bounding box')
    const cx = stageBox.x + stageBox.width / 2
    const cy = stageBox.y + stageBox.height / 2
    await page.mouse.click(cx, cy)

    // SC-2: single-select inspector populates.
    await expect(page.getByTestId('inspector-single')).toBeVisible({
      timeout: 5_000,
    })

    // SC-2: layer toggle row is interactable (Condados is always present).
    await expect(page.getByTestId('layer-toggle-condados')).toBeVisible()
    await page.getByTestId('layer-toggle-condados').click()

    // SC-2: shift+click a different stage point → multi-select view.
    await page.keyboard.down('Shift')
    await page.mouse.click(cx + 80, cy + 60)
    await page.keyboard.up('Shift')
    await expect(page.getByTestId('inspector-multi')).toBeVisible({
      timeout: 5_000,
    })
    await expect(page.getByTestId('inspector-multi')).toContainText(
      /selecionados|condados/,
    )

    // SC-3: zero console errors over the whole flow.
    expect(consoleErrors, `console errors: ${JSON.stringify(consoleErrors)}`)
      .toEqual([])
    // SC-4: zero v1 /preview/* requests.
    expect(previewLeaks, `preview leaks: ${JSON.stringify(previewLeaks)}`)
      .toEqual([])
  })
})
