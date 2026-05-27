/**
 * Phase 08 D-14: Copy Branch to Main dialog.
 * Red confirm — wholesale-replaces main after confirmation (D-14, no 3-way merge).
 *
 * Client-side implementation (planner pick per 08-09-PLAN.md §CopyBranchToMainDialog):
 *   1. useRestoreSnapshot(pid, sourceBranchId) → fetch latest snapshot payload
 *   2. useCreateSnapshot(pid, mainBranchId) with trigger='manual' + payload from source
 *   3. switchBranch('main', payload) to rehydrate store
 *
 * No backend endpoint file is listed in files_modified, confirming client-side path.
 */
import {
  Dialog,
  Button,
  Flex,
  Text,
  Callout,
} from '@radix-ui/themes';
import { useState } from 'react';

interface CopyBranchToMainDialogProps {
  open: boolean;
  sourceBranchId: string | null;
  sourceBranchName: string;
  mainBranchId: string | null;
  onConfirm: (sourceBranchId: string, mainBranchId: string) => Promise<void>;
  onCancel: () => void;
}

export function CopyBranchToMainDialog({
  open,
  sourceBranchId,
  sourceBranchName,
  mainBranchId,
  onConfirm,
  onCancel,
}: CopyBranchToMainDialogProps) {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    if (!sourceBranchId || !mainBranchId) return;
    setIsPending(true);
    setError(null);
    try {
      await onConfirm(sourceBranchId, mainBranchId);
    } catch (e) {
      setError((e as Error).message ?? 'Erro ao copiar para main.');
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
        maxWidth="440px"
        data-testid="copy-to-main-dialog"
      >
        <Dialog.Title color="red">Copiar para main</Dialog.Title>
        <Dialog.Description size="2" mb="4">
          A ramificação{' '}
          <Text weight="bold">&ldquo;{sourceBranchName}&rdquo;</Text>{' '}
          irá <Text weight="bold">substituir completamente</Text> o conteúdo de{' '}
          <Text weight="bold">main</Text>. Esta ação é irreversível — o estado
          atual de main será perdido.
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
            data-testid="copy-to-main-cancel-btn"
          >
            Cancelar
          </Button>
          <Button
            variant="solid"
            color="red"
            onClick={handleConfirm}
            loading={isPending}
            data-testid="copy-to-main-confirm-btn"
          >
            Confirmar — substituir main
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
