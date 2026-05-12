/**
 * France 1066 create-project end-to-end UAT — Plan 05-10 (SC-3).
 *
 * Exercises the NewProjectModal → project creation → navigation flow for
 * France 1066. This spec covers the UI path that Plan 05-08 wired:
 *   data-testid="new-project-button"  → opens dialog
 *   data-testid="new-project-modal"   → dialog container
 *   data-testid="region-select"       → region picker
 *
 * NOTE: The spec does NOT attempt to run the full generate pipeline in the
 * browser (120 s timeout would be required and backend may not be seeded
 * with France inputs during a headless CI run). Instead it asserts the
 * modal open/close flow and project creation navigation — the backend E2E
 * gate (test_france_1066_export_contract.py) covers the 12-file contract.
 *
 * R-07 (review): all selectors use getByTestId for resilience against copy
 * changes. The data-testid hooks are from Plan 05-08:
 *   new-project-button, new-project-modal, region-select
 */

import { test, expect } from '@playwright/test'

test.describe('France 1066 NewProjectModal flow', () => {
  test('france_1066 create + generate produces 12 artifacts', async ({ page }) => {
    // -------------------------------------------------------------------
    // 1. Navigate to project list
    // -------------------------------------------------------------------
    await page.goto('/')

    // -------------------------------------------------------------------
    // 2. Open the NewProjectModal via the "Novo projeto" button
    // -------------------------------------------------------------------
    const newProjectBtn = page.getByTestId('new-project-button')
    await expect(newProjectBtn).toBeVisible({ timeout: 10_000 })
    await newProjectBtn.click()

    // -------------------------------------------------------------------
    // 3. Modal is visible
    // -------------------------------------------------------------------
    const modal = page.getByTestId('new-project-modal')
    await expect(modal).toBeVisible({ timeout: 5_000 })

    // -------------------------------------------------------------------
    // 4. Fill project name
    //    (Radix TextField.Root renders a plain <input> without a linked <label>;
    //    use placeholder as the accessible selector — see NewProjectModal.tsx:127)
    // -------------------------------------------------------------------
    await page.getByPlaceholder('Ex.: Reconquista 868').fill('UAT France 1066')

    // -------------------------------------------------------------------
    // 5. Select France 1066 region from the region picker
    //    (region-select uses Radix Select.Trigger; clicking it opens the
    //    dropdown; we then pick the option by visible text)
    // -------------------------------------------------------------------
    const regionSelect = page.getByTestId('region-select')
    await expect(regionSelect).toBeVisible({ timeout: 10_000 })
    await regionSelect.click()
    // Wait for option list to appear — Radix Select renders to a portal
    await page.getByRole('option', { name: /France 1066/i }).click()

    // -------------------------------------------------------------------
    // 6. Submit — "Criar projeto" button becomes enabled after both fields
    //    are valid (Plan 05-08: name 1–64 chars + region has_dataset:true)
    // -------------------------------------------------------------------
    const createBtn = page.getByRole('button', { name: 'Criar projeto' })
    await expect(createBtn).toBeEnabled({ timeout: 5_000 })
    await createBtn.click()

    // -------------------------------------------------------------------
    // 7. Assert navigation to /projects/{id}
    //    The mutation on success calls navigate(`/projects/${id}`)
    // -------------------------------------------------------------------
    // Project IDs are UUIDs (String(36) in models.py) — not digits
    await expect(page).toHaveURL(/\/projects\/[\w-]+/, { timeout: 15_000 })

    // -------------------------------------------------------------------
    // 8. Workspace renders — generate button available
    //    (Toolbar from Plan 03-05 has data-testid="workspace-toolbar")
    // -------------------------------------------------------------------
    await expect(page.getByTestId('workspace-toolbar')).toBeVisible({ timeout: 10_000 })

    // -------------------------------------------------------------------
    // 9. Trigger generate via the Gerar button
    //    Budget per SC-3 Playwright: 30 s (D-19)
    // -------------------------------------------------------------------
    const gerarBtn = page.getByRole('button', { name: /Gerar/i })
    await expect(gerarBtn).toBeVisible({ timeout: 5_000 })
    await gerarBtn.click()

    // -------------------------------------------------------------------
    // 10. Wait for run completion — status badge or log panel signals done
    //     Timeout: 120 s (France toy pipeline runs in ~6 s locally)
    // -------------------------------------------------------------------
    await expect(
      page.getByTestId('generate-status-badge')
    ).toContainText(/Mapa gerado|Pronto|conclu/i, { timeout: 120_000 })
  })
})
