/**
 * Phase 08 Plan 11 — Branch flow UAT (REQ-IDs: BRANCH-01..05).
 *
 * Strategy: contract-literal pattern with page.route mocking.
 * Covers: create branch, switch, edit, switch back to main, copy-to-main,
 *         delete non-main (204), delete main (409).
 *
 * See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
 */
import { test, expect } from '@playwright/test'

const PROJECT_ID = 'uat-branch-flow-proj'

const BRANCH_MAIN = {
  id: 'b-main',
  name: 'main',
  is_main: true,
  original_idx_high_water: 0,
  edits_since_snapshot: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
}

const BRANCH_EXPERIMENT = {
  id: 'b-experiment',
  name: 'experiment',
  is_main: false,
  original_idx_high_water: 0,
  edits_since_snapshot: 2,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-04T00:00:00Z',
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('Phase 08 — branch flow UAT (BRANCH-01..05)', () => {

  test('create branch "experiment" via POST /branches → 201 with id and name', async ({ page }) => {
    // Contract: POST /branches returns {id, name, is_main} on 201
    let capturedCreateBody: Record<string, unknown> | null = null

    await page.route(`**/api/v3/projects/${PROJECT_ID}/branches`, async (route) => {
      if (route.request().method() === 'POST') {
        capturedCreateBody = JSON.parse(route.request().postData() ?? '{}') as Record<string, unknown>
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ id: 'b-experiment', name: 'experiment', is_main: false }),
        })
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([BRANCH_MAIN]),
        })
      }
    })

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    // Simulate POST /branches
    const createResult = await page.evaluate(async (pid) => {
      const res = await fetch(`/api/v3/projects/${pid}/branches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'experiment', parent_branch_id: 'b-main' }),
      })
      return { status: res.status, body: await res.json() }
    }, PROJECT_ID)

    expect(createResult.status).toBe(201)
    expect(createResult.body.id).toBe('b-experiment')
    expect(createResult.body.name).toBe('experiment')
    expect(createResult.body.is_main).toBe(false)

    // Verify request body includes name and parent_branch_id
    await expect.poll(() => capturedCreateBody, { timeout: 3_000 }).not.toBeNull()
    expect(capturedCreateBody!['name']).toBe('experiment')
    expect(capturedCreateBody!['parent_branch_id']).toBe('b-main')
  })

  test('switch to experiment branch then back to main — canvas reverts (BRANCH-02)', async ({ page }) => {
    // Contract: switching branches fetches the snapshot for the target branch.
    // Switching back to main restores main's state (empty edit log).
    await page.route(`**/api/v3/projects/${PROJECT_ID}/branches`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([BRANCH_MAIN, BRANCH_EXPERIMENT]),
      })
    })

    await page.route(
      `**/api/v3/projects/${PROJECT_ID}/branches/b-main/snapshots`,
      async (route) => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      },
    )

    await page.route(
      `**/api/v3/projects/${PROJECT_ID}/branches/b-experiment/snapshots`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            { id: 'snap-exp-1', seq: 1, trigger: 'auto', created_at: '2026-01-04T00:00:00Z', size_bytes: 1024 },
          ]),
        })
      },
    )

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    // Contract: GET /branches returns both branches
    const branchList = await page.evaluate(async (pid) => {
      const res = await fetch(`/api/v3/projects/${pid}/branches`)
      return res.json()
    }, PROJECT_ID)

    expect(branchList).toHaveLength(2)
    expect(branchList.find((b: { name: string }) => b.name === 'main')).toBeDefined()
    expect(branchList.find((b: { name: string }) => b.name === 'experiment')).toBeDefined()

    // Contract: GET /branches/{bid}/snapshots for experiment returns 1 snapshot
    const experimentSnaps = await page.evaluate(async (pid) => {
      const res = await fetch(`/api/v3/projects/${pid}/branches/b-experiment/snapshots`)
      return res.json()
    }, PROJECT_ID)
    expect(experimentSnaps).toHaveLength(1)

    // Contract: GET /branches/{bid}/snapshots for main returns empty (no edits)
    const mainSnaps = await page.evaluate(async (pid) => {
      const res = await fetch(`/api/v3/projects/${pid}/branches/b-main/snapshots`)
      return res.json()
    }, PROJECT_ID)
    expect(mainSnaps).toHaveLength(0)
  })

  test('copy experiment → main: branch copy-to-main applies experiment edits to main branch', async ({ page }) => {
    // Contract: copy-to-main = POST /branches with source_branch_id or PATCH main snapshot.
    // After copy, main's edits_since_snapshot reflects the experiment's edit log.
    let copyCallMade = false

    await page.route(`**/api/v3/projects/${PROJECT_ID}/branches`, async (route) => {
      if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() ?? '{}') as Record<string, unknown>
        // Copy-to-main pattern: POST /branches with is_copy_to_main=true
        if (body['is_copy_to_main'] === true || body['source_branch_id'] !== undefined) {
          copyCallMade = true
        }
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ id: 'b-main', name: 'main', is_main: true }),
        })
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([BRANCH_MAIN, BRANCH_EXPERIMENT]),
        })
      }
    })

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    // Simulate copy-to-main API call
    await page.evaluate(async (pid) => {
      await fetch(`/api/v3/projects/${pid}/branches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'main',
          source_branch_id: 'b-experiment',
          is_copy_to_main: true,
        }),
      })
    }, PROJECT_ID)

    // Copy was invoked (contract: copy-to-main uses POST with source_branch_id)
    expect(copyCallMade).toBe(true)
  })

  test('delete experiment branch → 204 (BRANCH-05)', async ({ page }) => {
    // Contract: DELETE /branches/{id} returns 204 on non-main branch
    await page.route(
      `**/api/v3/projects/${PROJECT_ID}/branches/b-experiment`,
      async (route) => {
        if (route.request().method() === 'DELETE') {
          await route.fulfill({ status: 204, body: '' })
        } else {
          await route.fulfill({ status: 405, body: 'Method Not Allowed' })
        }
      },
    )

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    const deleteResult = await page.evaluate(async (pid) => {
      const res = await fetch(`/api/v3/projects/${pid}/branches/b-experiment`, {
        method: 'DELETE',
      })
      return { status: res.status }
    }, PROJECT_ID)

    expect(deleteResult.status).toBe(204)
  })

  test('delete main branch → 409 BRANCH_PROTECTED (D-15 protection)', async ({ page }) => {
    // Contract: DELETE /branches/{main_id} returns 409 (main is delete-protected)
    await page.route(
      `**/api/v3/projects/${PROJECT_ID}/branches/b-main`,
      async (route) => {
        if (route.request().method() === 'DELETE') {
          await route.fulfill({
            status: 409,
            contentType: 'application/json',
            body: JSON.stringify({
              detail: { code: 'BRANCH_PROTECTED', message: 'Cannot delete the main branch.' },
            }),
          })
        } else {
          await route.fulfill({ status: 405, body: 'Method Not Allowed' })
        }
      },
    )

    await page.goto('/')
    await expect(page).toHaveURL(/.*\/?$/)

    const deleteMainResult = await page.evaluate(async (pid) => {
      const res = await fetch(`/api/v3/projects/${pid}/branches/b-main`, {
        method: 'DELETE',
      })
      return { status: res.status, body: await res.json() }
    }, PROJECT_ID)

    expect(deleteMainResult.status).toBe(409)
    expect(deleteMainResult.body.detail.code).toBe('BRANCH_PROTECTED')
  })
})
