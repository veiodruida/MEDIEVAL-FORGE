/* Wave 0 stub for Phase 08 — implemented in plan 08-09.
 * Covers REQ-IDs: BRANCH-01, BRANCH-02, BRANCH-04, UX-01
 * See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
 *
 * WARNING-6 wiring: WorkspaceToolbar mounts EditorSyncBridge when in
 * vertex-edit mode; BranchPicker triggers branch switch which clears
 * zundo temporal history.
 * Review-3: WorkspaceToolbar Undo/Redo tooltip reads undoLabels.at(-1).
 */
import { describe, it } from 'vitest';

describe('Phase 08 — BranchPicker (BRANCH-01, BRANCH-02, BRANCH-04)', () => {
  it.skip('TODO plan 08-09: BranchPicker lists all branches from GET /branches response', () => {});
  it.skip('TODO plan 08-09: selecting a branch dispatches switchBranch action and clears temporal history', () => {});
  it.skip('TODO plan 08-09: new branch dialog creates branch via POST /branches and selects it', () => {});
  it.skip('TODO plan 08-09: delete branch dialog calls DELETE /branches/{id} and removes entry from list', () => {});
  it.skip('TODO plan 08-09: undoLabels tooltip reads last entry from undoLabels stack', () => {});
});
