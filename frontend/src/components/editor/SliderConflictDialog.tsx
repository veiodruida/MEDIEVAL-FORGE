/**
 * Phase 08 D-19 + Pitfall 9: Slider Conflict dialog.
 * Opens AFTER auto-snapshot succeeds (201) — never before.
 *
 * Props: {open, branchName, snapshotSeq, onConfirm, onCancel}
 * onConfirm → proceed with slider render POST
 * onCancel  → revert slider value (caller responsibility per D-19)
 *
 * UI copy: per UI-SPEC §Slider Conflict Modal.
 * Pitfall 9 contract: callers (ParameterSidebar) must await useCreateSnapshot
 * before setting open=true. This component enforces nothing — the ordering
 * guarantee lives in ParameterSidebar's intercept logic.
 */
import {
  Dialog,
  Button,
  Flex,
  Text,
  Callout,
} from '@radix-ui/themes';

interface SliderConflictDialogProps {
  open: boolean;
  branchName: string;
  /** Snapshot sequence number that was saved before this dialog opened. Null if unknown. */
  snapshotSeq: number | null;
  onConfirm: () => void;
  onCancel: () => void;
}

export function SliderConflictDialog({
  open,
  branchName,
  snapshotSeq,
  onConfirm,
  onCancel,
}: SliderConflictDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onCancel(); }}>
      <Dialog.Content
        maxWidth="460px"
        data-testid="slider-conflict-dialog"
      >
        <Dialog.Title>Conflito com edições pendentes</Dialog.Title>
        <Dialog.Description size="2" mb="4">
          Você alterou um parâmetro enquanto há edições de vértices pendentes na
          ramificação{' '}
          <Text weight="bold">&ldquo;{branchName}&rdquo;</Text>.
        </Dialog.Description>

        {snapshotSeq !== null && (
          <Callout.Root color="green" size="1" mb="4">
            <Callout.Text>
              As edições foram salvas automaticamente no snapshot{' '}
              <Text weight="bold">#{snapshotSeq}</Text>. Você pode
              restaurá-las depois no histórico de snapshots.
            </Callout.Text>
          </Callout.Root>
        )}

        <Text size="2" color="gray" as="p" mb="4">
          Ao confirmar, as edições pendentes serão descartadas e o mapa será
          regenerado com o novo valor do parâmetro. Para reverter, restaure o
          snapshot #{snapshotSeq ?? '—'} no histórico de edições.
        </Text>

        <Flex gap="3" justify="end">
          <Button
            variant="outline"
            color="gray"
            onClick={onCancel}
            data-testid="slider-conflict-cancel-btn"
          >
            Cancelar — manter edições
          </Button>
          <Button
            variant="solid"
            color="red"
            onClick={onConfirm}
            data-testid="slider-conflict-confirm-btn"
          >
            Confirmar e regenerar
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
