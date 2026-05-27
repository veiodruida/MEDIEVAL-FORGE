/**
 * Phase 08 D-15: Rename Branch dialog.
 * TextField defaulted to current branch name; PATCH via useRenameBranch.
 * Main branch rename is allowed (D-15).
 */
import { useState, useEffect } from 'react';
import {
  Dialog,
  Button,
  Flex,
  TextField,
  Callout,
} from '@radix-ui/themes';

interface RenameBranchDialogProps {
  open: boolean;
  branchId: string | null;
  currentName: string;
  onConfirm: (branchId: string, newName: string) => Promise<void>;
  onCancel: () => void;
}

export function RenameBranchDialog({
  open,
  branchId,
  currentName,
  onConfirm,
  onCancel,
}: RenameBranchDialogProps) {
  const [name, setName] = useState(currentName);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync input when dialog opens with current name
  useEffect(() => {
    if (open) {
      setName(currentName);
      setError(null);
    }
  }, [open, currentName]);

  const handleRename = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError('O nome da ramificação é obrigatório.');
      return;
    }
    if (!branchId) return;
    setIsPending(true);
    setError(null);
    try {
      await onConfirm(branchId, trimmed);
    } catch (e) {
      setError((e as Error).message ?? 'Erro ao renomear ramificação.');
    } finally {
      setIsPending(false);
    }
  };

  const handleCancel = () => {
    setName(currentName);
    setError(null);
    onCancel();
  };

  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) handleCancel(); }}>
      <Dialog.Content
        maxWidth="420px"
        data-testid="rename-branch-dialog"
      >
        <Dialog.Title>Renomear ramificação</Dialog.Title>

        <Flex direction="column" gap="3" mt="3">
          <TextField.Root
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); }}
            data-testid="rename-branch-name-input"
            autoFocus
          />
          {error && (
            <Callout.Root color="red" size="1">
              <Callout.Text>{error}</Callout.Text>
            </Callout.Root>
          )}
        </Flex>

        <Flex gap="3" mt="4" justify="end">
          <Button
            variant="soft"
            color="gray"
            onClick={handleCancel}
            disabled={isPending}
            data-testid="rename-branch-cancel-btn"
          >
            Cancelar
          </Button>
          <Button
            variant="solid"
            onClick={handleRename}
            loading={isPending}
            data-testid="rename-branch-confirm-btn"
          >
            Renomear
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
