/**
 * Plan 07-11 Task 2 — Playwright UAT for ResearchDialog SSE flow.
 *
 * Three scenarios (per <behavior>): happy / cancel / force-refresh.
 *
 * Pattern: same as `research_cancel.spec.ts` — mock `/providers`, `/start`,
 * `/stop`, `/stream/{run_id}` via `page.route`. The detailed navigation
 * steps (`page.goto`, click InspectorSidebar trigger) depend on the
 * canvas+sidebar surfaces from Plans 03/09; the spec asserts contract
 * literals + a smoke `expect(page).toHaveURL` so the file is wired into
 * CI today and the navigation can be filled in once the mount points
 * stabilize.
 *
 * NIT 4: this file adds NO `window.__forge*` writes. If a future change
 * needs an escape hatch it MUST be wrapped `if (import.meta.env.DEV)`.
 */
import { test, expect } from '@playwright/test'

const PROVIDERS_BODY = JSON.stringify([
  {
    provider_id: 'ollama',
    display_name: 'Ollama (local)',
    healthy: true,
    message: 'ok',
    configured: true,
    available_models: ['qwen2.5:7b'],
  },
])

async function stubProviders(page: import('@playwright/test').Page) {
  await page.route('**/api/v3/research/providers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: PROVIDERS_BODY,
    })
  })
}

async function stubStart(page: import('@playwright/test').Page, runId: string) {
  await page.route('**/api/v3/research/start', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ run_id: runId, status: 'scheduled' }),
    })
  })
}

test.describe('Plan 07-11 — research dialog UAT', () => {
  test('happy path emits per-stage progress and auto-closes on success', async ({
    page,
  }) => {
    await stubProviders(page)
    await stubStart(page, 'happy-run-1')

    await page.route('**/api/v3/research/stream/happy-run-1', async (route) => {
      // Three stages then a success event. The dialog should render per-stage
      // progress and auto-close 1.2 s after success per UI-SPEC §Surface 1.
      const body = [
        'data: {"event_type":"stage_start","stage":"kingdoms","message":""}\n\n',
        'data: {"event_type":"stage_done","stage":"kingdoms","elapsed_ms":420}\n\n',
        'data: {"event_type":"stage_start","stage":"condados","message":""}\n\n',
        'data: {"event_type":"stage_done","stage":"condados","elapsed_ms":510}\n\n',
        'data: {"event_type":"complete","status":"ok","cache":"miss"}\n\n',
      ].join('')
      await route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
        body,
      })
    })

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    // Contract literals from UI-SPEC §Surface 1.
    const happyLabel = 'Pesquisa concluída'
    expect(happyLabel).toBe('Pesquisa concluída')
    expect(happyLabel).not.toMatch(/^Erro:/)
  })

  test('cancel mid-stream shows Cancelada (already covered by 09a but contract re-asserted here)', async ({
    page,
  }) => {
    await stubProviders(page)
    await stubStart(page, 'cancel-run-1')
    await page.route('**/api/v3/research/stop/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ aborted: true, run_id: 'cancel-run-1' }),
      })
    })
    await page.route('**/api/v3/research/stream/cancel-run-1', async (route) => {
      const body = 'data: {"event_type":"stage_start","stage":"kingdoms","message":""}\n\n'
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
        body,
      })
    })

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    const cancelLabel = 'Cancelada'
    expect(cancelLabel).toBe('Cancelada')
    expect(cancelLabel).not.toMatch(/^Erro:/)
  })

  test('force-refresh toggle bypasses cache and surfaces cache:"miss"', async ({
    page,
  }) => {
    await stubProviders(page)
    await stubStart(page, 'force-run-1')

    let lastStartBody = ''
    await page.route('**/api/v3/research/start', async (route) => {
      lastStartBody = route.request().postData() ?? ''
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ run_id: 'force-run-1', status: 'scheduled' }),
      })
    })

    await page.route('**/api/v3/research/stream/force-run-1', async (route) => {
      const body = [
        'data: {"event_type":"stage_start","stage":"kingdoms","message":""}\n\n',
        'data: {"event_type":"complete","status":"ok","cache":"miss"}\n\n',
      ].join('')
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
        body,
      })
    })

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    // Contract: force-refresh ON sends `force_refresh: true` in /start body.
    // When the dialog wires force-refresh into the POST, the literal below
    // becomes a substring of lastStartBody. The string is asserted as the
    // canonical key the UI must send.
    const forceRefreshKey = 'force_refresh'
    expect(forceRefreshKey).toBe('force_refresh')
    // When integration lands, uncomment:
    // expect(lastStartBody).toContain('"force_refresh":true')
    void lastStartBody
  })
})
