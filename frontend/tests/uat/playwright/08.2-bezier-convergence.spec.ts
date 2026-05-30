/**
 * Phase 08.2 Plan 01 — BEZ-CONV-05 UAT scaffold.
 *
 * SKIP-MARKED until Wave 2 (Plan 04 un-skips by removing test.describe.skip).
 *
 * // COASTLINE barony: "Gijón" — interior shared edges gap by construction — RESEARCH A3
 * Gijón is on the north coast of Iberia (lat ~43.54, lon ~-5.66). It has open sea boundary
 * on the north — no interior shared edges to gap when only one barony ring is re-rasterised.
 * This satisfies RESEARCH A3 (interior gaps are structural; UAT targets coastline only).
 *
 * Three assertions scaffolded as TODO/skip steps:
 *   (1) Overlay absent before first edit; present after first drag.
 *   (2) After Apply: colored barony boundary pixels change + overlay clears.
 *   (3) Reload page: boundary persists; export ZIP contains the changed lookup.
 *
 * Data-testid anchors (UI-SPEC §10):
 *   bezier-apply-edits-btn     — "Apply edits" button (manual mode trigger)
 *   bezier-apply-auto-switch   — auto-immediate mode toggle
 *   bezier-edited-contour      — the amber-dashed live overlay element
 *
 * REQ-IDs: BEZ-CONV-05
 */
import { readFileSync } from 'node:fs'
import { test, expect, type Page } from '@playwright/test'

// ─── Project info helper ──────────────────────────────────────────────────────

function loadProjectInfo(): { project_id: string; name: string } {
  const p = process.env.UAT_PROJECT_INFO_PATH
  if (!p) {
    throw new Error(
      'UAT_PROJECT_INFO_PATH is not set; globalSetup did not run. Did you launch via `npx playwright test`?',
    )
  }
  return JSON.parse(readFileSync(p, 'utf-8'))
}

// ─── BEZ-CONV-05: Bézier convergence end-to-end (skip until Wave 2) ──────────

// COASTLINE barony: "Gijón" — interior shared edges gap by construction — RESEARCH A3
const COASTLINE_BARONY = 'Gijón'

test.describe.skip('Phase 08.2 — BEZ-CONV-05: Bézier edit reaches colored map (Wave 2)', () => {
  /**
   * This describe block is skipped until Plan 04 (Wave 2) un-skips it.
   * Plan 04's job: implement the Apply button + auto-immediate toggle,
   * wire the snapshot POST + /render cascade, and verify convergence in browser.
   *
   * When un-skipped, these tests form the full convergence criterion:
   * G8 is closed when all three pass in a real browser with a real project.
   */

  // ── Assertion 1: overlay lifecycle ──────────────────────────────────────────

  test(
    'coastline: overlay absent before first edit AND present after first drag',
    async ({ page }: { page: Page }) => {
      // TODO (Wave 2 / Plan 04): implement this test.
      //
      // Setup:
      //   1. loadProjectInfo() to get project_id.
      //   2. Navigate to workspace; click edit-tool-v (vertex mode).
      //   3. Select COASTLINE_BARONY ("Gijón") via __forgeSelectBarony.
      //   4. Wait for anchorCount >= 4.
      //   5. Zoom to 6x; pan to first anchor.
      //
      // Assert BEFORE first drag:
      //   expect(page.getByTestId('bezier-edited-contour')).not.toBeVisible()
      //   OR assert editedContourPointCount === 0 via __forgeBezierState.
      //   (Plan 03 editLog>0 guard: overlay hidden when editLog is empty)
      //
      // First drag (real page.mouse events):
      //   await page.mouse.move(ax, ay)
      //   await page.mouse.down()
      //   await page.mouse.move(ax + 30, ay + 30, { steps: 8 })
      //   await page.mouse.up()
      //
      // Assert AFTER first drag:
      //   expect(page.getByTestId('bezier-edited-contour')).toBeVisible()
      //   AND editedContourPointCount > 0 via __forgeBezierState.

      const info = loadProjectInfo()
      void info // suppress unused variable warning — used above in TODO
      test.skip()
    },
  )

  // ── Assertion 2: Apply triggers convergence ──────────────────────────────────

  test(
    'coastline: after Apply, colored barony boundary pixels change AND overlay clears',
    async ({ page }: { page: Page }) => {
      // TODO (Wave 2 / Plan 04): implement this test.
      //
      // Setup:
      //   Same as assertion 1 setup above; perform one real drag to create an edit.
      //
      // Pre-Apply: capture baseline baronies.geojson ring for COASTLINE_BARONY
      //   const ringBefore = await fetchBaronyRing(page, project_id, COASTLINE_BARONY)
      //
      // Apply edits (manual mode):
      //   await page.getByTestId('bezier-apply-edits-btn').click()
      //   // Wait for render cascade to complete (SSE stream, ~5s)
      //   await page.waitForResponse(resp => resp.url().includes('/render') && resp.ok())
      //
      // Assert colored boundary changed (baroniesQ auto-refetched on render success):
      //   const ringAfter = await fetchBaronyRing(page, project_id, COASTLINE_BARONY)
      //   expect(ringAfter).not.toBe(ringBefore)
      //
      // Assert overlay cleared (clear-on-converge):
      //   expect(page.getByTestId('bezier-edited-contour')).not.toBeVisible()
      //   OR editedContourPointCount === 0 via __forgeBezierState.
      //
      // auto-immediate mode alternative:
      //   Toggle bezier-apply-auto-switch ON before the drag.
      //   The cascade fires automatically on each committed edit.

      const info = loadProjectInfo()
      void info
      test.skip()
    },
  )

  // ── Assertion 3: Persistence + export ────────────────────────────────────────

  test(
    'coastline: after Apply + reload, boundary persists AND export ZIP contains changed lookup',
    async ({ page }: { page: Page }) => {
      // TODO (Wave 2 / Plan 04): implement this test.
      //
      // Setup:
      //   Perform one real drag + Apply (same as assertion 2).
      //   Capture the barony ring after Apply for comparison.
      //
      // Reload:
      //   await page.reload()
      //   // Wait for canvas to re-hydrate
      //   await expect(page.getByTestId('canvas-stage')).toBeVisible({ timeout: 15_000 })
      //
      // Assert boundary persists:
      //   const ringAfterReload = await fetchBaronyRing(page, project_id, COASTLINE_BARONY)
      //   expect(ringAfterReload).toBe(ringAfterApply) // same geometry survives reload
      //
      // Assert export ZIP contains changed lookup_barony.png:
      //   const zipUrl = `/api/v3/projects/${project_id}/export`
      //   const zipResp = await page.request.get(zipUrl)
      //   // Extract lookup_barony.png from ZIP and compare pixel at barony centroid
      //   // to the pre-edit golden fixture — must differ.
      //   // (Exact implementation depends on Plan 04's export endpoint contract.)

      const info = loadProjectInfo()
      void info
      test.skip()
    },
  )
})
