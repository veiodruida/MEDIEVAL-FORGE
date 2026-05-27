/**
 * Phase 08 D-11 + D-13: New Branch dialog.
 * Radix Dialog with TextField + Criar/Cancelar buttons.
 * Calls useCreateBranch on confirm; on success closes dialog and notifies parent.
 *
 * UI copy: per UI-SPEC §New Branch Dialog.
 */
import { useState } from 'react';
import {
  Dialog,
  Button,
  Flex,
  Text,
  TextField,
  Callout,
} from '@radix-ui/themes';

interface NewBranchDialogProps {
  open: boolean;
  currentBranchId: string | null;
  onConfirm: (name: string, parentBranchId: string | null) => Promise<void>;
  onCancel: () => void;
}

export function NewBranchDialog({
  open,
  currentBranchId,
  onConfirm,
  onCancel,
}: NewBranchDialogProps) {
  const [name, setName] = useState('');
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError('O nome da ramificação é obrigatório.');
      return;
    }
    setIsPending(true);
    setError(null);
    try {
      await onConfirm(trimmed, currentBranchId);
      setName('');
    } catch (e) {
      setError((e as Error).message ?? 'Erro ao criar ramificação.');
    } finally {
      setIsPending(false);
    }
  };

  const handleCancel = () => {
    setName('');
    setError(null);
    onCancel();
  };

  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) handleCancel(); }}>
      <Dialog.Content
        maxWidth="420px"
        data-testid="new-branch-dialog"
      >
        <Dialog.Title>Nova ramificação</Dialog.Title>
        <Dialog.Description size="2" mb="4" color="gray">
          Crie uma ramificação a partir do estado atual de{' '}
          <Text weight="bold">
            {currentBranchId ? 'da ramificação ativa' : 'main'}
          </Text>
          .
        </Dialog.Description>

        <Flex direction="column" gap="3">
          <TextField.Root
            placeholder="Nome da ramificação"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleCreate(); }}
            data-testid="new-branch-name-input"
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
            data-testid="new-branch-cancel-btn"
          >
            Cancelar
          </Button>
          <Button
            variant="solid"
            onClick={handleCreate}
            loading={isPending}
            data-testid="new-branch-create-btn"
          >
            Criar
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
