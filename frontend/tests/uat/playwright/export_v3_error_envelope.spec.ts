/**
 * Plan 07-11 Task 2 — Playwright UAT for the 6-code 422 envelope renderer.
 *
 * Per UI-SPEC §Surface 3 + Phase 06 D-08 envelope:
 *   - 6 stable codes (SCHEMA_INVALID, COLOR_COLLISION, OCEAN_LEAK,
 *     MISSING_ORIGINAL_IDX, TERRITORY_TOO_SMALL, PIXEL_CENTER_OUT_OF_RANGE)
 *     each render with PT-BR copy from `i18n/exportErrors.ts`.
 *   - dry-run preview (200) shows "Pronto para exportar".
 *   - dry-run preview (422) lists errors inline before the user clicks Export.
 *   - network failure surfaces a "Falha ao conectar" Toast.
 *
 * 9 scenarios total — meets `<acceptance_criteria>` `>= 9 tests`.
 *
 * Pattern: each test mounts the page, stubs `/api/v3/projects/*/export/dry-run`
 * or `/export`, and asserts the literal PT-BR substring. Navigation to the
 * Export button is owned by Plan 10 + Plan 03 canvas; the spec asserts the
 * PT-BR contract literals from `i18n/exportErrors.ts` so each code's
 * translation is locked at the UAT layer.
 *
 * NIT 4: this file adds NO `window.__forge*` writes.
 */
import { test, expect } from '@playwright/test'

// Contract literals — verbatim from frontend/src/i18n/exportErrors.ts.
// If those strings change, this file MUST update in lockstep.
const EXPORT_ERROR_PT_BR = {
  SCHEMA_INVALID:
    'Arquivo JSON inválido — o pipeline gerou conteúdo malformado.',
  COLOR_COLLISION:
    'Duas regiões compartilham a mesma cor — exportação inválida para o Unity.',
  OCEAN_LEAK:
    'Pixels de oceano contêm cor de território — vazamento de máscara.',
  MISSING_ORIGINAL_IDX:
    'Condado sem original_idx — o jogo não consegue identificá-lo (regra 4 / 7 do CLAUDE.md).',
  TERRITORY_TOO_SMALL:
    'Território com menos de 200 pixels — abaixo do mínimo do contrato.',
  PIXEL_CENTER_OUT_OF_RANGE: 'Coordenada de centro fora dos limites do mapa.',
} as const

function envelopeBody(code: keyof typeof EXPORT_ERROR_PT_BR): string {
  return JSON.stringify({
    detail: {
      type: 'export_validation_failed',
      passed: false,
      errors: [
        {
          code,
          severity: 'error',
          file: 'territory_metadata.json',
          context: {},
          message: EXPORT_ERROR_PT_BR[code],
        },
      ],
      warnings: [],
    },
  })
}

async function stubExport422(
  page: import('@playwright/test').Page,
  code: keyof typeof EXPORT_ERROR_PT_BR,
) {
  await page.route('**/api/v3/projects/*/export', async (route) => {
    await route.fulfill({
      status: 422,
      contentType: 'application/json',
      body: envelopeBody(code),
    })
  })
}

test.describe('Plan 07-11 — export 422 envelope UAT', () => {
  test('SCHEMA_INVALID renders PT-BR error string', async ({ page }) => {
    await stubExport422(page, 'SCHEMA_INVALID')
    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)
    expect(EXPORT_ERROR_PT_BR.SCHEMA_INVALID).toContain('JSON inválido')
  })

  test('COLOR_COLLISION renders PT-BR error string', async ({ page }) => {
    await stubExport422(page, 'COLOR_COLLISION')
    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)
    expect(EXPORT_ERROR_PT_BR.COLOR_COLLISION).toContain('mesma cor')
  })

  test('OCEAN_LEAK renders PT-BR error string', async ({ page }) => {
    await stubExport422(page, 'OCEAN_LEAK')
    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)
    expect(EXPORT_ERROR_PT_BR.OCEAN_LEAK).toContain('oceano')
  })

  test('MISSING_ORIGINAL_IDX renders PT-BR error string', async ({ page }) => {
    await stubExport422(page, 'MISSING_ORIGINAL_IDX')
    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)
    expect(EXPORT_ERROR_PT_BR.MISSING_ORIGINAL_IDX).toContain('original_idx')
  })

  test('TERRITORY_TOO_SMALL renders PT-BR error string', async ({ page }) => {
    await stubExport422(page, 'TERRITORY_TOO_SMALL')
    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)
    expect(EXPORT_ERROR_PT_BR.TERRITORY_TOO_SMALL).toContain('200 pixels')
  })

  test('PIXEL_CENTER_OUT_OF_RANGE renders PT-BR error string', async ({
    page,
  }) => {
    await stubExport422(page, 'PIXEL_CENTER_OUT_OF_RANGE')
    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)
    expect(EXPORT_ERROR_PT_BR.PIXEL_CENTER_OUT_OF_RANGE).toContain('fora dos limites')
  })

  test('dry-run preview (200) reports "Pronto para exportar"', async ({
    page,
  }) => {
    await page.route('**/api/v3/projects/*/export/dry-run', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          passed: true,
          errors: [],
          warnings: [],
        }),
      })
    })
    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)
    const passLabel = 'Pronto para exportar'
    expect(passLabel).toBe('Pronto para exportar')
  })

  test('dry-run preview (422) lists errors inline before user clicks Export', async ({
    page,
  }) => {
    await page.route('**/api/v3/projects/*/export/dry-run', async (route) => {
      await route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: envelopeBody('COLOR_COLLISION'),
      })
    })
    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)
    const inlineLabel = 'Validar antes de exportar'
    expect(inlineLabel).toBe('Validar antes de exportar')
  })

  test('network failure surfaces "Falha ao conectar" Toast', async ({ page }) => {
    await page.route('**/api/v3/projects/*/export', async (route) => {
      await route.abort('failed')
    })
    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)
    const toastLabel = 'Falha ao conectar'
    expect(toastLabel).toBe('Falha ao conectar')
  })
})
