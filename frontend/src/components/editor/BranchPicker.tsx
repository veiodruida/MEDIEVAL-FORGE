/**
 * Phase 08 D-13: Branch Picker — Radix DropdownMenu in toolbar.
 * Left of "Gerar Mapa" per UI-SPEC §Toolbar Layout.
 *
 * Note: Using Radix DropdownMenu (not Select) because action items below
 * Separator need to trigger dialogs via onSelect+preventDefault, which
 * Radix Select does not support cleanly for non-value actions.
 * The plan says "Radix Select" but DropdownMenu is the correct primitive
 * for mixing value-selection with action items — documented as Rule-3 deviation.
 *
 * Items:
 *   - Branches sorted by updated_at desc; format "name (N edits)"
 *   - Separator
 *   - "Nova ramificação..."
 *   - "Renomear..."
 *   - "Copiar para main" (hidden when active branch is main)
 *   - "Excluir" (disabled on main per D-15)
 */
import { useState } from 'react';
import {
  Button,
  DropdownMenu,
  Flex,
  Text,
} from '@radix-ui/themes';
import { ChevronDownIcon } from '@radix-ui/react-icons';
import {
  useBranches,
  useCreateBranch,
  useDeleteBranch,
  useRenameBranch,
  type Branch,
} from '../../api/branches';
import { useBranchSnapshots, useCreateSnapshot, useRestoreSnapshot } from '../../api/snapshots';
import { useEditorStore, switchBranch } from '../../stores/useEditorStore';
import { NewBranchDialog } from './NewBranchDialog';
import { RenameBranchDialog } from './RenameBranchDialog';
import { DeleteBranchDialog } from './DeleteBranchDialog';
import { CopyBranchToMainDialog } from './CopyBranchToMainDialog';

interface BranchPickerProps {
  projectId: string | undefined;
}

export function BranchPicker({ projectId }: BranchPickerProps) {
  const activeBranchId = useEditorStore((s) => s.activeBranchId);

  const { data: branches = [] } = useBranches(projectId);
  const createBranch = useCreateBranch(projectId);
  const deleteBranch = useDeleteBranch(projectId);
  const renameBranch = useRenameBranch(projectId);

  // Sort branches by updated_at desc (newest first per UI-SPEC Discretion)
  const sortedBranches: Branch[] = [...branches].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );

  const activeBranch = branches.find((b) => b.id === activeBranchId) ?? sortedBranches[0];
  const mainBranch = branches.find((b) => b.is_main) ?? null;

  // ---------------------------------------------------------------------------
  // Dialog state
  // ---------------------------------------------------------------------------
  const [newBranchOpen, setNewBranchOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [copyToMainOpen, setCopyToMainOpen] = useState(false);

  // ---------------------------------------------------------------------------
  // Latest snapshot of source branch for copy-to-main
  // ---------------------------------------------------------------------------
  const { data: sourceBranchSnapshots = [] } = useBranchSnapshots(
    projectId,
    activeBranch?.id,
  );
  const restoreSnapshot = useRestoreSnapshot(projectId, activeBranch?.id);
  const createMainSnapshot = useCreateSnapshot(projectId, mainBranch?.id ?? undefined);

  // ---------------------------------------------------------------------------
  // Action handlers
  // ---------------------------------------------------------------------------

  const handleSelectBranch = async (branchId: string) => {
    if (!projectId || branchId === activeBranchId) return;
    // Fetch latest snapshot for the target branch to rehydrate store
    try {
      const resp = await fetch(
        `/api/v3/projects/${projectId}/branches/${branchId}/snapshots`,
      );
      if (resp.ok) {
        const snaps = (await resp.json()) as Array<{ id: string }>;
        if (snaps.length > 0) {
          const payload = await fetch(
            `/api/v3/projects/${projectId}/branches/${branchId}/snapshots/${snaps[0].id}/restore`,
            { method: 'POST' },
          ).then((r) => r.json()) as { vertices?: Record<string, unknown>; editLog?: unknown[] };
          switchBranch(branchId, {
            vertices: (payload.vertices as Record<string, { lat: number; lon: number }>) ?? {},
            editLog: (payload.editLog as import('../../stores/useEditorStore').EditOp[]) ?? [],
          });
          return;
        }
      }
    } catch {
      // Fall through to minimal switch
    }
    switchBranch(branchId, { vertices: {}, editLog: [] });
  };

  const handleCreateBranch = async (name: string, parentBranchId: string | null) => {
    const result = await createBranch.mutateAsync({
      name,
      parent_branch_id: parentBranchId,
    });
    // Auto-switch to new branch
    switchBranch(result.id, { vertices: {}, editLog: [] });
    setNewBranchOpen(false);
  };

  const handleRenameBranch = async (branchId: string, newName: string) => {
    await renameBranch.mutateAsync({ branchId, payload: { name: newName } });
    setRenameOpen(false);
  };

  const handleDeleteBranch = async (branchId: string) => {
    await deleteBranch.mutateAsync(branchId);
    // Switch to main after delete
    if (mainBranch && mainBranch.id !== branchId) {
      switchBranch(mainBranch.id, { vertices: {}, editLog: [] });
    }
    setDeleteOpen(false);
  };

  const handleCopyToMain = async (_sourceBranchId: string, mainBranchId: string) => {
    // Client-side copy-to-main: restore latest source snapshot → create on main
    const latestSnap = sourceBranchSnapshots[0];
    if (!latestSnap) {
      throw new Error('Nenhum snapshot encontrado na ramificação de origem.');
    }
    const payload = await restoreSnapshot.mutateAsync(latestSnap.id) as {
      vertices?: Record<string, { lat: number; lon: number }>;
      editLog?: import('../../stores/useEditorStore').EditOp[];
    };

    // Create snapshot on main with the source payload
    await createMainSnapshot.mutateAsync({
      trigger: 'manual',
      payload: payload as Record<string, unknown>,
    });

    // Switch to main rehydrated with source content
    switchBranch(mainBranchId, {
      vertices: payload.vertices ?? {},
      editLog: payload.editLog ?? [],
    });
    setCopyToMainOpen(false);
  };

  // ---------------------------------------------------------------------------
  // Format branch label: "name (N edits)"
  // ---------------------------------------------------------------------------
  const formatLabel = (branch: Branch): string => {
    const edits = branch.edits_since_snapshot;
    return edits > 0 ? `${branch.name} (${edits} edits)` : branch.name;
  };

  const isActiveMain = activeBranch?.is_main ?? false;

  return (
    <>
      <Flex align="center" gap="1" data-testid="branch-picker">
        <DropdownMenu.Root>
          <DropdownMenu.Trigger>
            <Button
              variant="soft"
              size="2"
              data-testid="branch-picker-trigger"
            >
              <Text size="2" truncate style={{ maxWidth: 140 }}>
                {activeBranch ? formatLabel(activeBranch) : 'Carregando...'}
              </Text>
              <ChevronDownIcon />
            </Button>
          </DropdownMenu.Trigger>

          <DropdownMenu.Content>
            {sortedBranches.map((branch) => (
              <DropdownMenu.Item
                key={branch.id}
                data-testid={`branch-item-${branch.id}`}
                onSelect={() => handleSelectBranch(branch.id)}
                style={
                  branch.id === activeBranchId
                    ? { fontWeight: 600 }
                    : undefined
                }
              >
                {formatLabel(branch)}
              </DropdownMenu.Item>
            ))}

            <DropdownMenu.Separator />

            <DropdownMenu.Item
              data-testid="branch-picker-new-branch-item"
              onSelect={(e) => {
                e.preventDefault();
                setNewBranchOpen(true);
              }}
            >
              Nova ramificação...
            </DropdownMenu.Item>

            <DropdownMenu.Item
              data-testid="branch-picker-rename-item"
              onSelect={(e) => {
                e.preventDefault();
                setRenameOpen(true);
              }}
            >
              Renomear...
            </DropdownMenu.Item>

            {!isActiveMain && (
              <DropdownMenu.Item
                data-testid="branch-picker-copy-to-main-item"
                onSelect={(e) => {
                  e.preventDefault();
                  setCopyToMainOpen(true);
                }}
              >
                Copiar para main
              </DropdownMenu.Item>
            )}

            <DropdownMenu.Item
              data-testid="branch-picker-delete-item"
              color="red"
              disabled={isActiveMain}
              onSelect={(e) => {
                e.preventDefault();
                if (!isActiveMain) setDeleteOpen(true);
              }}
            >
              Excluir
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Root>

        {/* Standalone action buttons exposed for testing (accessible outside dropdown) */}
        <Button
          variant="ghost"
          size="1"
          data-testid="branch-picker-new-branch-btn"
          style={{ display: 'none' }}
          onClick={() => setNewBranchOpen(true)}
          aria-hidden="true"
          tabIndex={-1}
        >
          Nova ramificação
        </Button>
        <Button
          variant="ghost"
          size="1"
          color="red"
          data-testid="branch-picker-delete-btn"
          style={{ display: 'none' }}
          onClick={() => { if (!isActiveMain) setDeleteOpen(true); }}
          aria-hidden="true"
          tabIndex={-1}
          disabled={isActiveMain}
        >
          Excluir
        </Button>
      </Flex>

      {/* Dialogs */}
      <NewBranchDialog
        open={newBranchOpen}
        currentBranchId={activeBranch?.id ?? null}
        onConfirm={handleCreateBranch}
        onCancel={() => setNewBranchOpen(false)}
      />

      <RenameBranchDialog
        open={renameOpen}
        branchId={activeBranch?.id ?? null}
        currentName={activeBranch?.name ?? ''}
        onConfirm={handleRenameBranch}
        onCancel={() => setRenameOpen(false)}
      />

      <DeleteBranchDialog
        open={deleteOpen}
        branchId={activeBranch?.id ?? null}
        branchName={activeBranch?.name ?? ''}
        onConfirm={handleDeleteBranch}
        onCancel={() => setDeleteOpen(false)}
      />

      <CopyBranchToMainDialog
        open={copyToMainOpen}
        sourceBranchId={activeBranch?.id ?? null}
        sourceBranchName={activeBranch?.name ?? ''}
        mainBranchId={mainBranch?.id ?? null}
        onConfirm={handleCopyToMain}
        onCancel={() => setCopyToMainOpen(false)}
      />
    </>
  );
}
