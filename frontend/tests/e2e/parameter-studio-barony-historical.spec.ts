import { readFileSync } from 'node:fs'
import { test, expect } from '@playwright/test'

/**
 * Plan 04.1-05 SC-3 (D-03) acceptance spec: selecting a barony surfaces the
 * InspectorSidebar barony branch with source coordinate (lat/lon to 3
 * decimals), source-file label (literal `inicio/territory_data_v3.py`),
 * and collapsible "Sobre o método" explainer.
 *
 * Click-target strategy: rather than guessing a pixel coordinate that lands
 * on a specific barony in the seeded Iberia 868 geometry, this spec uses the
 * `window.__forgeSelectBarony` development-only escape hatch (exposed by
 * BaronyLayer.tsx, gated on `import.meta.env.DEV`, mitigates T-04.1-05-01).
 * The barony name "Betanzos" is a known centroid in inicio/territory_data_v3.py
 * (DUCADO DE GALIZA, condado Coruña) and emits a centroid via the post-04.1
 * canvas_sidecars.py.
 */
function loadProjectInfo(): { project_id: string; name: string } {
  const p = process.env.UAT_PROJECT_INFO_PATH
  if (!p) throw new Error('UAT_PROJECT_INFO_PATH not set; globalSetup did not run.')
  return JSON.parse(readFileSync(p, 'utf-8'))
}

test.describe('Parameter Studio SC-3 barony historical panel (D-03)', () => {
  test('clicking a barony surfaces source-coord, source-file, and explainer', async ({ page }) => {
    const info = loadProjectInfo()
    await page.goto(`/projects/${info.project_id}`)

    await expect(page.getByTestId('canvas-stage')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('inspector-sidebar')).toBeVisible({ timeout: 10_000 })

    // Wait until the dev-only __forgeSelectBarony hook is exposed by the
    // BaronyLayer's useEffect. Per Plan 04.1-05 Task 3 T-04.1-05-01 mitigation
    // the hook is gated on import.meta.env.DEV.
    await page.waitForFunction(
      () =>
        typeof (window as { __forgeSelectBarony?: unknown }).__forgeSelectBarony ===
        'function',
      { timeout: 10_000 },
    )

    // Select a known barony from the seeded Iberia 868 dataset
    // (DUCADO DE GALIZA, condado Coruña). Betanzos is one of three baronies
    // in that condado and has a real centroid in inicio/territory_data_v3.py.
    await page.evaluate(() => {
      ;(
        window as { __forgeSelectBarony?: (name: string) => void }
      ).__forgeSelectBarony?.('Betanzos')
    })

    // The inspector should switch to the barony branch.
    await expect(page.getByTestId('inspector-barony')).toBeVisible({ timeout: 5_000 })

    // Source coordinate row visible with numeric content (lat, lon to 3
    // decimals). Match "-NN.NNN, -NN.NNN" pattern.
    const coordEl = page.getByTestId('barony-source-coord')
    await expect(coordEl).toBeVisible()
    const coordText = (await coordEl.textContent()) ?? ''
    expect(
      coordText.trim(),
      `Source coordinate did not render as 'lat, lon' to 3 decimals: got '${coordText.trim()}'`,
    ).toMatch(/^-?\d+\.\d{3},\s*-?\d+\.\d{3}$/)

    // Source file label visible with the literal canonical path.
    const sourceFile = page.getByTestId('barony-source-file')
    await expect(sourceFile).toBeVisible()
    await expect(sourceFile).toHaveText('inicio/territory_data_v3.py')

    // Collapsible explainer present with the PT-BR Voronoi-from-centroids
    // explanation (always in the DOM via <details>; user-agent CSS hides
    // until <summary> click but text node is queryable).
    const explainer = page.getByTestId('barony-method-explainer')
    await expect(explainer).toBeVisible()
    await expect(explainer).toContainText('centroides históricos')
    await expect(explainer).toContainText('Voronoi')
  })
})
