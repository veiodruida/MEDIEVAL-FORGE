/**
 * Phase 07.1 Plan 09 Task 2 — Playwright UAT: numeric period inputs (SC-1 e2e).
 *
 * Two specs verifying that ResearchDialog renders two numeric inputs and that
 * the submit payload sends period_start / period_end as JSON integers (not
 * period_label string).
 *
 * Navigation: uses the same harness route as llamacpp_launch.spec.ts.
 *   page.goto('/test-research-dialog?projectId=p1')
 *   The harness renders <ResearchDialog open={true} /> directly.
 *
 * useProject uses the v1 legacy route: GET /api/projects/:id (NOT /api/v3/projects/:id).
 * useProviders: GET /api/v3/research/providers — must return healthy: true so that
 *   pickDefaultProvider() sets a non-empty provider, enabling canSubmit.
 */
import { test, expect } from '@playwright/test'

const TEST_PROJECT_ID = 'p1'
const HARNESS_URL = `/test-research-dialog?projectId=${TEST_PROJECT_ID}`

test.describe('ResearchDialog — numeric period inputs (SC-1 e2e)', () => {
  test.beforeEach(async ({ page }) => {
    // useProject v1 legacy route
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

    // Providers: healthy=true so pickDefaultProvider() enables canSubmit
    await page.route('**/api/v3/research/providers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            provider_id: 'llamacpp',
            display_name: 'Llama.cpp (local)',
            healthy: true,
            message: '',
            configured: true,
            available_models: ['Qwen3-7B-Q4.gguf'],
          },
        ]),
      })
    })

    // Research overlay (keep idle — no overlay for p1)
    await page.route('**/api/v3/research/overlay/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ exists: false }),
      })
    })

    // llama.cpp status (not running — AuthSetupSheet not open in these specs)
    await page.route('**/api/v3/llm/llamacpp/launch', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ running: false }),
        })
      }
    })
  })

  test('two numeric inputs render and seed from Project.period_start/end', async ({ page }) => {
    await page.goto(HARNESS_URL)

    const start = page.getByTestId('research-period-start')
    const end = page.getByTestId('research-period-end')

    await expect(start).toBeVisible()
    await expect(start).toHaveAttribute('type', 'number')
    await expect(start).toHaveAttribute('min', '1')
    await expect(start).toHaveAttribute('max', '2100')
    await expect(start).toHaveValue('868')
    await expect(end).toHaveValue('1000')
  })

  test('submit payload sends period_start and period_end as integers (not period_label)', async ({
    page,
  }) => {
    let capturedBody: Record<string, unknown> | null = null

    await page.route('**/api/v3/research/start', async (route) => {
      capturedBody = JSON.parse(route.request().postData() ?? '{}') as Record<string, unknown>
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ run_id: 'p1', status: 'scheduled' }),
      })
    })

    await page.goto(HARNESS_URL)

    // Wait for provider query to settle (so canSubmit becomes true)
    await page.waitForTimeout(300)

    // Click the submit button — "Iniciar pesquisa" per UI-SPEC §Surface 1 CTA copy
    await page.getByRole('button', { name: /iniciar pesquisa/i }).click()

    // Wait for the POST to be captured
    await expect.poll(() => capturedBody, { timeout: 5_000 }).not.toBeNull()

    expect(capturedBody!['period_start']).toBe(868)
    expect(typeof capturedBody!['period_start']).toBe('number')
    expect(capturedBody!['period_end']).toBe(1000)
    expect(capturedBody).not.toHaveProperty('period_label')
  })
})
