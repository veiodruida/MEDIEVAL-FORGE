/**
 * Phase 08 D-15: Delete Branch dialog.
 * Red confirm per UI-SPEC §Delete Branch Dialog.
 * Main branch is delete-protected (disabled in picker, never opens for main).
 * DELETE via useDeleteBranch; on success parent should switch to main.
 */
import {
  Dialog,
  Button,
  Flex,
  Text,
  Callout,
} from '@radix-ui/themes';
import { useState } from 'react';

interface DeleteBranchDialogProps {
  open: boolean;
  branchId: string | null;
  branchName: string;
  onConfirm: (branchId: string) => Promise<void>;
  onCancel: () => void;
}

export function DeleteBranchDialog({
  open,
  branchId,
  branchName,
  onConfirm,
  onCancel,
}: DeleteBranchDialogProps) {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async () => {
    if (!branchId) return;
    setIsPending(true);
    setError(null);
    try {
      await onConfirm(branchId);
    } catch (e) {
      setError((e as Error).message ?? 'Erro ao excluir ramificação.');
      setIsPending(false);
    }
  };

  const handleCancel = () => {
    setError(null);
    onCancel();
  };

  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) handleCancel(); }}>
      <Dialog.Content
        maxWidth="420px"
        data-testid="delete-branch-dialog"
      >
        <Dialog.Title color="red">Excluir ramificação</Dialog.Title>
        <Dialog.Description size="2" mb="4">
          Tem certeza que deseja excluir a ramificação{' '}
          <Text weight="bold">&ldquo;{branchName}&rdquo;</Text>?
          Esta ação é irreversível — todos os snapshots desta ramificação serão perdidos.
        </Dialog.Description>

        {error && (
          <Callout.Root color="red" size="1" mb="3">
            <Callout.Text>{error}</Callout.Text>
          </Callout.Root>
        )}

        <Flex gap="3" mt="2" justify="end">
          <Button
            variant="soft"
            color="gray"
            onClick={handleCancel}
            disabled={isPending}
            data-testid="delete-branch-cancel-btn"
          >
            Cancelar
          </Button>
          <Button
            variant="solid"
            color="red"
            onClick={handleDelete}
            loading={isPending}
            data-testid="delete-branch-confirm-btn"
          >
            Excluir ramificação
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
