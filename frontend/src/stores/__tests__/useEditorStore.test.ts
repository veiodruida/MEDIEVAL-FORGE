/* Wave 0 stub for Phase 08 — implemented in plan 08-04.
 * Covers REQ-IDs: UNDO-01, EDIT-VERTEX-03, PERSIST-02
 * See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
 *
 * WARNING-6 fix: setVerticesAndLog is the single sink chokepoint for all
 * vertex mutations; undoLabels/redoLabels stacks tracked in lockstep with
 * zundo temporal history.
 */
import { describe, it } from 'vitest';

describe('Phase 08 — useEditorStore (UNDO-01, EDIT-VERTEX-03)', () => {
  it.skip('TODO plan 08-04: zundo temporal wraps store; pastStates grows on moveVertex', () => {});
  it.skip('TODO plan 08-04: history cap = 100; oldest entry evicted on push past cap', () => {});
  it.skip('TODO plan 08-04: switchBranch() clears temporal history and resets pastStates to []', () => {});
  it.skip('TODO plan 08-04: setVerticesAndLog is single sink chokepoint — all vertex mutations route through it', () => {});
  it.skip('TODO plan 08-04: undoLabels stack grows one entry per moveVertex call with descriptive label', () => {});
  it.skip('TODO plan 08-04: redoLabels stack clears when a new edit is applied after undo', () => {});
});
