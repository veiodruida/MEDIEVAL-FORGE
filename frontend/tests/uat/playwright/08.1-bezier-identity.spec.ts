/**
 * Phase 08.1 Plan 04 — BEZ-UAT-02: identity-through-export gate (SLOW, phase-gate only).
 *
 * The end-to-end port of the Phase 08 parity test
 * `test_empty_edit_log_preserves_lookup_barony_png`: entering and EXITING Bézier edit
 * mode with ZERO drags must leave the exported `lookup_barony.png` byte-for-byte
 * identical to the pre-edit baseline. This is the T-08.1-04-02 tampering mitigation —
 * the curve-fit/flatten round trip must never silently rewrite geometry that reaches
 * the Unity export. It complements the Plan 02 unit-level BEZ-IDENTITY-01 (store-level)
 * by proving the guarantee survives all the way through the real export pipeline.
 *
 * Marked @slow (full export run): the phase gate runs it explicitly.
 *
 * Flow:
 *   1. Open the seeded Iberia 868 project; wait for the canvas to hydrate.
 *   2. Capture pre-edit lookup_barony.png SHA-256 (artifact fetch).
 *   3. Enter Bézier edit mode: V tool + select a barony → anchors fit (no store write).
 *   4. Exit edit mode WITHOUT dragging (clear selection / switch tool).
 *   5. Trigger export (POST /export) and re-fetch lookup_barony.png SHA-256.
 *   6. Assert the two SHA-256 hashes are identical.
 *
 * REQ-IDs: BEZ-UAT-02
 */
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { test, expect, type Page } from '@playwright/test'

function loadProjectInfo(): { project_id: string; name: string } {
  const p = process.env.UAT_PROJECT_INFO_PATH
  if (!p) {
    throw new Error(
      'UAT_PROJECT_INFO_PATH is not set; globalSetup did not run. Did you launch via `npx playwright test`?',
    )
  }
  return JSON.parse(readFileSync(p, 'utf-8'))
}

/** Fetch lookup_barony.png through the running app and return its SHA-256 hex digest. */
async function lookupBaronySha(page: Page, projectId: string): Promise<string> {
  const b64 = await page.evaluate(async (pid) => {
    const res = await fetch(`/api/v3/projects/${pid}/artifacts/lookup_barony.png`)
    if (!res.ok) throw new Error(`artifact fetch failed: ${res.status}`)
    const buf = new Uint8Array(await res.arrayBuffer())
    let binary = ''
    for (let i = 0; i < buf.length; i++) binary += String.fromCharCode(buf[i])
    return btoa(binary)
  }, projectId)
  return createHash('sha256').update(Buffer.from(b64, 'base64')).digest('hex')
}

async function discoverBaronyId(page: Page, projectId: string): Promise<string> {
  const id = await page.evaluate(async (pid) => {
    const res = await fetch(`/api/v3/projects/${pid}/artifacts/baronies.geojson`)
    if (!res.ok) return null
    const fc = await res.json()
    const feat = fc?.features?.[0]
    return (feat?.id ?? feat?.properties?.id ?? feat?.properties?.name ?? null) as string | null
  }, projectId)
  if (!id) throw new Error('Could not discover a barony id from seeded baronies.geojson')
  return id
}

test.describe('Phase 08.1 — BEZ-UAT-02 identity through export', () => {
  test('@slow enter+exit Bézier mode with zero drags → lookup_barony.png SHA-256 unchanged', async ({
    page,
  }) => {
    test.setTimeout(180_000) // full export pipeline run

    const info = loadProjectInfo()
    await page.goto(`/projects/${info.project_id}`)
    await expect(page.getByTestId('canvas-stage')).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId('territory-layer-ready')).toBeAttached({ timeout: 30_000 })

    // 2. Pre-edit baseline SHA-256.
    const baselineSha = await lookupBaronySha(page, info.project_id)
    expect(baselineSha).toMatch(/^[0-9a-f]{64}$/)

    // 3. Enter Bézier mode: V tool + select a barony (anchors fit on entry; no store write).
    await expect(page.getByTestId('edit-tool-palette')).toBeVisible()
    await page.getByTestId('edit-tool-v').click()
    const baronyId = await discoverBaronyId(page, info.project_id)
    await page.evaluate((id) => {
      ;(window as unknown as { __forgeSelectBarony?: (id: string) => void }).__forgeSelectBarony?.(id)
    }, baronyId)

    // Confirm the layer actually mounted (otherwise the round trip proves nothing).
    await expect
      .poll(
        async () =>
          page.evaluate(() => {
            const fn = (window as unknown as { __forgeBezierState?: () => { anchorCount: number } })
              .__forgeBezierState
            return fn ? fn().anchorCount : 0
          }),
        { timeout: 15_000 },
      )
      .toBeGreaterThanOrEqual(4)

    // 4. Exit WITHOUT dragging: switch off the V tool (Esc) — no flatten, no commit.
    await page.getByTestId('edit-tool-esc').click()

    // 5. Trigger the real export and re-fetch the artifact SHA-256.
    const exportStatus = await page.evaluate(async (pid) => {
      const res = await fetch(`/api/v3/projects/${pid}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      return res.status
    }, info.project_id)
    expect([200, 201]).toContain(exportStatus)

    const afterSha = await lookupBaronySha(page, info.project_id)

    // 6. Byte-identity: a zero-drag edit-mode round trip must not change the export.
    expect(afterSha, 'lookup_barony.png changed after a zero-drag Bézier round trip').toBe(
      baselineSha,
    )
  })
})
