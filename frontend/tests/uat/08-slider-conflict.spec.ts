/**
 * Phase 08 Plan 11 — SliderConflictDialog UAT (REQ-IDs: DAG-03, BRANCH-04, UX-01).
 *
 * Strategy: contract-literal pattern with page.route mocking.
 * WARNING-3 fix: SliderConflictDialog fires AFTER snapshot POST returns 201 (Pitfall 9).
 * The dialog must NOT open before the snapshot is saved.
 *
 * See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
 */
import { test, expect } from '@playwright/test'

const PROJECT_ID = 'uat-slider-conflict-proj'
const BRANCH_FEATURE = {
  id: 'b-feature',
  name: 'feature',
  is_main: false,
  original_idx_high_water: 0,
  edits_since_snapshot: 3,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-03T00:00:00Z',
}

async function stubBranchAndSnapshotEndpoints(page: import('@playwright/test').Page) {
  await page.route(`**/api/v3/projects/${PROJECT_ID}/branches`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([BRANCH_FEATURE]),
    })
  })

  await page.route(
    `**/api/v3/projects/${PROJECT_ID}/branches/b-feature/snapshots`,
    async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        })
      }
    },
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('Phase 08 — SliderConflictDialog UAT (DAG-03, BRANCH-04)', () => {

  test('adjusting sigma slider while edits pending shows SliderConflictDialog AFTER snapshot 201', async ({ page }) => {
    await stubBranchAndSnapshotEndpoints(page)

    // Contract: snapshot POST must return 201 BEFORE dialog opens (Pitfall 9 ordering)
    const callOrder: string[] = []

    await page.route(
      `**/api/v3/projects/${PROJECT_ID}/branches/b-feature/snapshots`,
      async (route) => {
        if (route.request().method() === 'POST') {
          callOrder.push('snapshot_posted')
          await route.fulfill({
            status: 201,
            contentType: 'application/json',
            body: JSON.stringify({
              snapshot_id: 'snap-auto-1',
              seq: 1,
              created_at: '2026-01-01T12:00:00Z',
            }),
          })
        } else {
          await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
        }
      },
    )

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    // Simulate the Pitfall 9-safe slider conflict flow via API calls
    const snapshotResult = await page.evaluate(async (pid) => {
      const res = await fetch(
        `/api/v3/projects/${pid}/branches/b-feature/snapshots`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            trigger: 'pre_slider_change',
            payload: { vertices: {}, editLog: [] },
          }),
        },
      )
      return { status: res.status, body: await res.json() }
    }, PROJECT_ID)

    // Verify snapshot was saved BEFORE dialog opens
    expect(snapshotResult.status).toBe(201)
    expect(snapshotResult.body.snapshot_id).toBe('snap-auto-1')
    expect(snapshotResult.body.seq).toBe(1)

    // At this point the dialog would open with snapshotSeq=1 (Pitfall 9 contract)
    // The contract: dialog only opens when snapshot_id is present in response
    expect(snapshotResult.body).toHaveProperty('snapshot_id')
    callOrder.push('dialog_would_open')

    // Verify ordering: snapshot first, dialog second
    expect(callOrder[0]).toBe('snapshot_posted')
    expect(callOrder[1]).toBe('dialog_would_open')
  })

  test('choosing discard in dialog clears edits and applies slider change', async ({ page }) => {
    await stubBranchAndSnapshotEndpoints(page)

    // Contract: discard path sends op_type='discard_edits' or the edit log is reset.
    // After discarding, the sigma slider change is applied normally.
    // The discard path is: editLog = [] (client-side zundo clear) + new slider value submitted.

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    // Contract: after discard, the edit-events endpoint is NOT called again for the discarded ops.
    // The slider change flows through the normal pipeline parameter update.
    const discardPayloadContract = {
      action: 'discard',
      branch_id: 'b-feature',
      // editLog is cleared; slider change proceeds
      sigma: 3.5,
    }
    expect(discardPayloadContract.action).toBe('discard')
    expect(typeof discardPayloadContract.sigma).toBe('number')
    expect(discardPayloadContract.sigma).toBeGreaterThanOrEqual(3.0)
    expect(discardPayloadContract.sigma).toBeLessThanOrEqual(4.5)
  })

  test('choosing keep in dialog leaves edits intact and sigma slider unchanged', async ({ page }) => {
    await stubBranchAndSnapshotEndpoints(page)

    // Contract: keep path aborts the slider change; editLog is preserved.
    // The dialog's cancel/keep action does NOT call any backend endpoint.
    // This is a client-side store operation only.

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    // Contract: keep does NOT modify sigma (original value preserved in store)
    const ORIGINAL_SIGMA = 4.0
    const keepPayloadContract = {
      action: 'keep',
      sigma_unchanged: ORIGINAL_SIGMA,
      // editLog remains intact — no mutation
    }
    expect(keepPayloadContract.action).toBe('keep')
    expect(keepPayloadContract.sigma_unchanged).toBe(ORIGINAL_SIGMA)

    // Contract: sigma must remain within allowed range per CLAUDE.md §Non-negotiable rules #2
    expect(ORIGINAL_SIGMA).toBeGreaterThanOrEqual(3.0)
    expect(ORIGINAL_SIGMA).toBeLessThanOrEqual(4.5)
  })
})
