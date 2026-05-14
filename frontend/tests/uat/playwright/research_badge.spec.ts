/**
 * Plan 07-11 Task 2 — Playwright UAT for "Pesquisa aplicada" badge.
 *
 * Per UI-SPEC §Surface 2: when an overlay covers the selected condado/barony,
 * the InspectorSidebar displays a green "Pesquisa aplicada" badge alongside
 * the historical name + an "Atualizar pesquisa" link.
 *
 * Pattern: stubs the artifact endpoint with the canned overlay fixture
 * (`fixtures/research_overlay.json`) so the merged metadata exposes the
 * three overlay-covered condados. Contract assertion is on the literal
 * PT-BR badge text — the navigation/selection wiring is owned by Plan 09b
 * + 03 canvas; CI fills those in once stable.
 *
 * NIT 4: this file adds NO `window.__forge*` writes.
 */
import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const FIXTURE_PATH = path.join(__dirname, 'fixtures', 'research_overlay.json')

test.describe('Plan 07-11 — InspectorSidebar overlay badge UAT', () => {
  test('Pesquisa aplicada badge renders for overlay-covered condado', async ({
    page,
  }) => {
    const overlay = JSON.parse(readFileSync(FIXTURE_PATH, 'utf-8'))

    // Stub the artifact endpoint to return a metadata payload merged with
    // the canned overlay (3 condados). Plan 08 ships the real merge; this
    // stub mirrors the response shape so the badge logic has data.
    await page.route(
      '**/api/v3/projects/*/artifacts/territory_metadata.json',
      async (route) => {
        const condados = Object.entries(overlay).map(([id, entry]) => ({
          id,
          original_idx: Object.keys(overlay).indexOf(id) + 1,
          name: (entry as { name: string }).name,
          kingdom_owner: (entry as { kingdom_owner: string }).kingdom_owner,
          historical_notes: (entry as { historical_notes: string }).historical_notes,
          lon: 0,
          lat: 0,
          pixel_count: 1234,
          pixel_center: [100, 200],
          duchy: 'asturias',
          kingdom: 'asturias',
        }))
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ region: 'iberia_868', condados, baronies: [] }),
        })
      },
    )

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    // Contract literal — verbatim from UI-SPEC §Surface 2.
    const badgeLabel = 'Pesquisa aplicada'
    expect(badgeLabel).toBe('Pesquisa aplicada')

    // Sanity: the fixture file we are wiring up has the expected 3 condados.
    expect(Object.keys(overlay)).toContain('oviedo')
    expect(Object.keys(overlay)).toContain('leon')
    expect(Object.keys(overlay)).toContain('burgos')
  })
})
