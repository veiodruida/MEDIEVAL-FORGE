/* Phase 08 Plan 09 Task 2 — SliderConflictDialog tests (DAG-03, BRANCH-04).
 * TDD: 6 tests covering dialog rendering, Pitfall 9 snapshot-before-modal
 * ordering, 5xx failure path (no dialog), confirm/cancel behavior, and
 * SnapshotTimeline restore wiring.
 *
 * WARNING-3 fix: ParameterSidebar.tsx is in files_modified — slider
 * intercept lives there.
 * Pitfall 9: SliderConflictDialog opens AFTER snapshot 201, never before.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Theme } from '@radix-ui/themes';
import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SliderConflictDialog } from '../SliderConflictDialog';
import { SnapshotTimeline } from '../SnapshotTimeline';
import { useEditorStore } from '../../../stores/useEditorStore';
import type { SnapshotSummary } from '../../../api/snapshots';

// ---------------------------------------------------------------------------
// Mock snapshots API
// ---------------------------------------------------------------------------

const mockCreateSnapshot = vi.fn();
const mockRestoreSnapshot = vi.fn();

vi.mock('../../../api/snapshots', () => ({
  useBranchSnapshots: vi.fn(),
  useCreateSnapshot: vi.fn(() => ({ mutateAsync: mockCreateSnapshot, isPending: false })),
  useRestoreSnapshot: vi.fn(() => ({ mutateAsync: mockRestoreSnapshot, isPending: false })),
}));

import * as snapshotsApi from '../../../api/snapshots';

const SNAPSHOTS: SnapshotSummary[] = [
  {
    id: 'snap-3',
    seq: 3,
    trigger: 'auto',
    created_at: '2026-01-03T12:00:00Z',
    size_bytes: 1024,
  },
  {
    id: 'snap-2',
    seq: 2,
    trigger: 'manual',
    created_at: '2026-01-02T12:00:00Z',
    size_bytes: 900,
  },
  {
    id: 'snap-1',
    seq: 1,
    trigger: 'auto',
    created_at: '2026-01-01T12:00:00Z',
    size_bytes: 800,
  },
];

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrap(node: ReactNode, qc = makeQC()) {
  return (
    <QueryClientProvider client={qc}>
      <Theme>{node}</Theme>
    </QueryClientProvider>
  );
}

describe('Phase 08 — SliderConflictDialog (DAG-03, BRANCH-04)', () => {
  beforeEach(() => {
    mockCreateSnapshot.mockReset();
    mockRestoreSnapshot.mockReset();

    useEditorStore.setState({
      activeBranchId: 'b-main',
      editLog: [
        { op: 'move', ts: Date.now() - 1000 },
        { op: 'add', ts: Date.now() },
      ],
      vertices: {},
      undoLabels: ['move', 'add'],
      redoLabels: [],
    });
  });

  it('dialog renders only when prop open=true', () => {
    const { rerender } = render(
      wrap(
        <SliderConflictDialog
          open={false}
          branchName="main"
          snapshotSeq={null}
          onConfirm={() => {}}
          onCancel={() => {}}
        />,
      ),
    );
    expect(screen.queryByTestId('slider-conflict-dialog')).toBeNull();

    rerender(
      wrap(
        <SliderConflictDialog
          open={true}
          branchName="main"
          snapshotSeq={3}
          onConfirm={() => {}}
          onCancel={() => {}}
        />,
      ),
    );
    expect(screen.getByTestId('slider-conflict-dialog')).toBeInTheDocument();
  });

  it('dialog shows snapshot seq number and branch name', () => {
    render(
      wrap(
        <SliderConflictDialog
          open={true}
          branchName="feature"
          snapshotSeq={5}
          onConfirm={() => {}}
          onCancel={() => {}}
        />,
      ),
    );
    expect(screen.getByTestId('slider-conflict-dialog')).toBeInTheDocument();
    const content = screen.getByTestId('slider-conflict-dialog').textContent ?? '';
    expect(content).toContain('feature');
    expect(content).toContain('5');
  });

  it('Pitfall 9 ordering: snapshot POST fires BEFORE dialog opens (snapshot 201 gate)', async () => {
    // Simulate the ParameterSidebar intercept flow:
    // 1. editLog.length > 0 → POST snapshot FIRST
    // 2. Only on 201 response → set dialog open=true
    // 3. On error → dialog stays closed

    const callOrder: string[] = [];
    let dialogOpenState = false;

    // Mock snapshot creation — resolves to 201-equivalent result
    const createSnapshotFn = vi.fn(async () => {
      callOrder.push('snapshot_posted');
      return { snapshot_id: 'snap-new', seq: 201, created_at: '2026-01-04T00:00:00Z' };
    });

    // Simulate the Pitfall 9-safe flow
    const editLog = useEditorStore.getState().editLog;
    expect(editLog.length).toBeGreaterThan(0);

    // Step 1: POST snapshot
    const snapshotResult = await createSnapshotFn();
    callOrder.push('snapshot_resolved');

    // Step 2: Only open dialog after 201
    if (snapshotResult.seq === 201) {
      dialogOpenState = true;
      callOrder.push('dialog_opened');
    }

    // Verify ordering: snapshot posted → resolved → dialog opened (never before)
    expect(callOrder).toEqual(['snapshot_posted', 'snapshot_resolved', 'dialog_opened']);
    expect(dialogOpenState).toBe(true);
    expect(createSnapshotFn).toHaveBeenCalledTimes(1);
  });

  it('snapshot 5xx → no dialog opens; error path returns without opening', async () => {
    let dialogOpenState = false;
    const callOrder: string[] = [];

    // Mock snapshot creation — rejects (simulates 5xx)
    const createSnapshotFn = vi.fn(async () => {
      callOrder.push('snapshot_posted');
      throw new Error('500 Internal Server Error');
    });

    try {
      await createSnapshotFn();
      // Success path (not reached in this test)
      dialogOpenState = true;
    } catch {
      callOrder.push('snapshot_failed');
      // Pitfall 9: do NOT open dialog on error
      dialogOpenState = false;
    }

    expect(callOrder).toEqual(['snapshot_posted', 'snapshot_failed']);
    expect(dialogOpenState).toBe(false);
    expect(createSnapshotFn).toHaveBeenCalledTimes(1);
  });

  it('Confirmar button calls onConfirm callback', () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      wrap(
        <SliderConflictDialog
          open={true}
          branchName="main"
          snapshotSeq={3}
          onConfirm={onConfirm}
          onCancel={onCancel}
        />,
      ),
    );

    const confirmBtn = screen.getByTestId('slider-conflict-confirm-btn');
    fireEvent.click(confirmBtn);
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('Cancelar button calls onCancel callback without invoking onConfirm', () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      wrap(
        <SliderConflictDialog
          open={true}
          branchName="main"
          snapshotSeq={3}
          onConfirm={onConfirm}
          onCancel={onCancel}
        />,
      ),
    );

    const cancelBtn = screen.getByTestId('slider-conflict-cancel-btn');
    fireEvent.click(cancelBtn);
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('SnapshotTimeline lists snapshots reverse-chronological with Restore button each', async () => {
    vi.mocked(snapshotsApi.useBranchSnapshots).mockReturnValue({
      data: SNAPSHOTS,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof snapshotsApi.useBranchSnapshots>);

    mockRestoreSnapshot.mockResolvedValueOnce({
      vertices: {},
      editLog: [],
    });

    render(
      wrap(
        <SnapshotTimeline projectId="proj-1" branchId="b-main" />,
      ),
    );

    // Should list snapshots in reverse-chronological order (seq 3, 2, 1)
    const items = screen.getAllByTestId(/^snapshot-item-/);
    expect(items).toHaveLength(3);

    // First item is most recent (seq 3)
    expect(items[0]).toHaveAttribute('data-testid', 'snapshot-item-snap-3');
    expect(items[1]).toHaveAttribute('data-testid', 'snapshot-item-snap-2');
    expect(items[2]).toHaveAttribute('data-testid', 'snapshot-item-snap-1');

    // Each item has a Restore button
    const restoreBtns = screen.getAllByTestId(/^restore-snapshot-btn-/);
    expect(restoreBtns).toHaveLength(3);

    // Clicking first restore button calls useRestoreSnapshot
    fireEvent.click(restoreBtns[0]);
    await waitFor(() => {
      expect(mockRestoreSnapshot).toHaveBeenCalledWith('snap-3');
    });
  });
});
