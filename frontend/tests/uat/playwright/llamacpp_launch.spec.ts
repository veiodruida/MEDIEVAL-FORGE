/**
 * Phase 07.1 Plan 09 Task 1 — Playwright UAT: llama.cpp launch flow (SC-5d).
 *
 * Three specs using Playwright route interception (no real llama-server spawned).
 *
 * Navigation strategy (review-fix #6 — harness fallback chosen):
 *   ProjectDetail mounts CanvasViewer + artifacts pipeline (many endpoints).
 *   Instead, specs navigate to /test-research-dialog?projectId=p1 which renders
 *   <ResearchDialog open={true} /> directly without the canvas surface.
 *   The harness file (frontend/src/test-routes/research-dialog.tsx) satisfies the
 *   "data-testid=research-dialog-entry exists in frontend/src/" acceptance criterion.
 *   The spec uses page.goto('/test-research-dialog?projectId=p1') as entry point.
 *
 * Endpoints mocked via page.route():
 *   GET /api/projects/p1              → Project shape (useProject v1 legacy route)
 *   GET /api/v3/research/providers    → [llamacpp provider]
 *   GET /api/v3/research/overlay/:id  → { exists: false }
 *   POST /api/v3/llm/llamacpp/launch  → LaunchResult or 409
 *   DELETE /api/v3/llm/llamacpp/launch → { ok: true, was_running: true }
 *   GET /api/v3/llm/llamacpp/launch   → running status (useLlamacppStatus)
 */
import { test, expect } from '@playwright/test'

const TEST_PROJECT_ID = 'p1'
const HARNESS_URL = `/test-research-dialog?projectId=${TEST_PROJECT_ID}`

type LaunchSuccessResponse = {
  ok: boolean
  base_url: string
  pid: number
  model: string
  started_at: string
}

type LaunchConflictResponse = {
  status: number
  detail: string
}

async function setupBackendMocks(
  page: import('@playwright/test').Page,
  opts: {
    availableModels?: string[]
    healthy?: boolean
    binaryMissing?: boolean
    launchResponse?: LaunchSuccessResponse | LaunchConflictResponse
  } = {},
) {
  const models = opts.availableModels ?? ['Qwen3-7B-Q4.gguf', 'Llama3.1-8B-Q4.gguf']
  const healthy = opts.healthy ?? false
  const binaryMissingMessage = opts.binaryMissing
    ? "llama-server não encontrado no PATH (defina LLAMA_SERVER_BIN)"
    : "Servidor llama-server não está ativo. Use 'Levantar servidor'."

  // useProject uses legacy v1 route
  await page.route('**/api/projects/p1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'p1',
        name: 'Iberia',
        period_start: 868,
        period_end: 1000,
        country_qid: 'Q29',
        region_key: 'iberia_868',
        status: 'ready',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      }),
    })
  })

  // Research providers (used by ResearchDialog + AuthSetupSheet)
  await page.route('**/api/v3/research/providers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          provider_id: 'llamacpp',
          display_name: 'Llama.cpp (local)',
          healthy,
          message: binaryMissingMessage,
          configured: true,
          available_models: models,
        },
      ]),
    })
  })

  // Research overlay (useResearchOverlay — returns "no overlay" to keep dialog idle)
  await page.route('**/api/v3/research/overlay/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ exists: false }),
    })
  })

  // llama.cpp launch/shutdown/status endpoints
  await page.route('**/api/v3/llm/llamacpp/launch', async (route) => {
    const method = route.request().method()

    if (method === 'POST') {
      const lr = opts.launchResponse
      if (lr && 'status' in lr) {
        // Conflict response
        await route.fulfill({
          status: (lr as LaunchConflictResponse).status,
          contentType: 'application/json',
          body: JSON.stringify({ detail: (lr as LaunchConflictResponse).detail }),
        })
      } else {
        const success: LaunchSuccessResponse = (lr as LaunchSuccessResponse | undefined) ?? {
          ok: true,
          base_url: 'http://127.0.0.1:38291',
          pid: 12345,
          model: 'Qwen3-7B-Q4.gguf',
          started_at: '2026-05-15T15:00:00Z',
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(success),
        })
      }
    } else if (method === 'DELETE') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, was_running: true }),
      })
    } else if (method === 'GET') {
      // useLlamacppStatus polls this; initially not running
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ running: false }),
      })
    }
  })
}

test.describe('AuthSetupSheet — llama.cpp launch flow (SC-5d)', () => {
  test('happy path: open AuthSetupSheet → select model → Levantar servidor → status active → Parar servidor', async ({
    page,
  }) => {
    await setupBackendMocks(page)

    // After launch succeeds, status poll should return running
    let launched = false
    await page.route('**/api/v3/llm/llamacpp/launch', async (route) => {
      const method = route.request().method()
      if (method === 'POST') {
        launched = true
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            base_url: 'http://127.0.0.1:38291',
            pid: 12345,
            model: 'Qwen3-7B-Q4.gguf',
            started_at: '2026-05-15T15:00:00Z',
          }),
        })
      } else if (method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(
            launched
              ? { running: true, base_url: 'http://127.0.0.1:38291', pid: 12345 }
              : { running: false },
          ),
        })
      } else if (method === 'DELETE') {
        launched = false
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ok: true, was_running: true }),
        })
      }
    })

    // Harness route (review-fix #6 fallback — see file header)
    await page.goto(HARNESS_URL)

    // Click "Configurar provedores" rodapé link to open AuthSetupSheet
    await page.getByTestId('auth-setup-sheet-trigger').click()
    await expect(page.getByTestId('auth-setup-sheet')).toBeVisible()
    await expect(page.getByTestId('tab-llamacpp')).toContainText('Llama.cpp local')
    await expect(page.getByTestId('tab-claude-disabled')).toBeDisabled()
    await expect(page.getByTestId('tab-ollama-disabled')).toBeDisabled()

    // Select model
    await page.getByTestId('llamacpp-model-select').click()
    await page.getByTestId('model-option-Qwen3-7B-Q4.gguf').click()

    // Click Levantar servidor
    await page.getByTestId('launch-button').click()

    // Status line transitions to running
    await expect(page.getByTestId('server-status-line')).toContainText(/Servidor ativo/i, {
      timeout: 10_000,
    })
    await expect(page.getByTestId('server-status-line')).toContainText('38291')

    // Button swap
    await expect(page.getByTestId('shutdown-button')).toContainText('Parar servidor')

    // Stop
    await page.getByTestId('shutdown-button').click()
    await expect(page.getByTestId('server-status-line')).toContainText('Nenhum servidor ativo', {
      timeout: 10_000,
    })
  })

  test('empty-models-hint is shown when dropdown is disabled', async ({ page }) => {
    await setupBackendMocks(page, { availableModels: [] })

    await page.goto(HARNESS_URL)
    await page.getByTestId('auth-setup-sheet-trigger').click()
    await expect(page.getByTestId('llamacpp-model-select')).toBeDisabled()
    await expect(page.getByTestId('empty-models-hint')).toContainText('Coloque arquivos .gguf')
  })

  test('HTTP 409 conflict renders PT-BR error containing "ativo" and "pare"', async ({ page }) => {
    await setupBackendMocks(page, {
      launchResponse: {
        status: 409,
        detail: 'modelo `existing.gguf` ativo — pare-o antes via DELETE',
      },
    })

    await page.goto(HARNESS_URL)
    await page.getByTestId('auth-setup-sheet-trigger').click()
    await page.getByTestId('llamacpp-model-select').click()
    await page.getByTestId('model-option-Qwen3-7B-Q4.gguf').click()
    await page.getByTestId('launch-button').click()

    const errorEl = page.getByTestId('launch-error')
    await expect(errorEl).toBeVisible()
    await expect(errorEl).toContainText(/ativo/i)
    await expect(errorEl).toContainText(/pare/i)
  })
})
