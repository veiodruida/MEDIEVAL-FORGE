/* Wave 0 stub for Phase 08 — implemented in plan 08-11.
 * Covers REQ-IDs: PERF-01, EDIT-VERTEX-01
 * See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
 *
 * Review-4 (Gemini + OpenCode review): snap-jitter zoom check (UAT step 5b)
 * and --allow-manual-override perf flag for CI flakiness mitigation.
 * Usage: ALLOW_MANUAL_OVERRIDE=1 npx playwright test tests/uat/08-perf-drag-60fps.spec.ts
 */
import { test } from '@playwright/test';

test.skip('TODO plan 08-11: drag 200 vertices measures avg frame time <= 16ms at default zoom', async ({ page }) => {});
test.skip('TODO plan 08-11: drag performance acceptable at 4x zoom (scale-aware snap, no jitter)', async ({ page }) => {});
test.skip('TODO plan 08-11: ALLOW_MANUAL_OVERRIDE=1 flag allows CI to waive 60fps gate in constrained environments', async ({ page }) => {});
