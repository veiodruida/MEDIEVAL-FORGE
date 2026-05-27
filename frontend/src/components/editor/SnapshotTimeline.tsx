/**
 * Phase 08 RESEARCH Open Q3: Snapshot Timeline.
 * Floating Card listing snapshots reverse-chronologically with Restore button each.
 *
 * Renders inside the InspectorSidebar editor panel "Histórico de Edições" section
 * (per UI-SPEC §Editor Panel).
 *
 * Restore flow (D-12 + PERSIST-02):
 *   1. useRestoreSnapshot(pid, bid).mutateAsync(snapshotId) → payload
 *   2. switchBranch(branchId, payload) to rehydrate store + clear zundo history
 */
import { Card, Flex, Text, Button, Badge } from '@radix-ui/themes';
import { useBranchSnapshots, useRestoreSnapshot } from '../../api/snapshots';
import { switchBranch } from '../../stores/useEditorStore';
import type { VertexCoord, EditOp } from '../../stores/useEditorStore';

interface SnapshotTimelineProps {
  projectId: string | undefined;
  branchId: string | null | undefined;
}

const TRIGGER_LABEL: Record<string, string> = {
  auto: 'Automático',
  manual: 'Manual',
  pre_slider_change: 'Antes do slider',
};

export function SnapshotTimeline({ projectId, branchId }: SnapshotTimelineProps) {
  const { data: snapshots = [], isLoading } = useBranchSnapshots(
    projectId,
    branchId ?? undefined,
  );

  const restore = useRestoreSnapshot(projectId, branchId ?? undefined);

  const handleRestore = async (snapshotId: string) => {
    if (!branchId) return;
    try {
      const payload = await restore.mutateAsync(snapshotId) as {
        vertices?: Record<string, VertexCoord>;
        editLog?: EditOp[];
      };
      switchBranch(branchId, {
        vertices: payload.vertices ?? {},
        editLog: payload.editLog ?? [],
      });
    } catch (err) {
      console.error('[SnapshotTimeline] restore failed', err);
    }
  };

  if (isLoading) {
    return (
      <Card data-testid="snapshot-timeline" size="1">
        <Text size="2" color="gray">Carregando histórico...</Text>
      </Card>
    );
  }

  if (snapshots.length === 0) {
    return (
      <Card data-testid="snapshot-timeline" size="1">
        <Text size="2" color="gray">Nenhum snapshot salvo ainda.</Text>
      </Card>
    );
  }

  return (
    <Card data-testid="snapshot-timeline" size="1">
      <Text size="2" weight="bold" mb="2" as="div">
        Histórico de Snapshots
      </Text>
      <Flex direction="column" gap="2">
        {snapshots.map((snap) => {
          const date = new Date(snap.created_at).toLocaleString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          });
          return (
            <Flex
              key={snap.id}
              align="center"
              justify="between"
              gap="2"
              data-testid={`snapshot-item-${snap.id}`}
            >
              <Flex direction="column" gap="1">
                <Flex align="center" gap="2">
                  <Text size="2" weight="medium">
                    #{snap.seq}
                  </Text>
                  <Badge
                    size="1"
                    color={snap.trigger === 'auto' ? 'gray' : 'blue'}
                    variant="soft"
                  >
                    {TRIGGER_LABEL[snap.trigger] ?? snap.trigger}
                  </Badge>
                </Flex>
                <Text size="1" color="gray">
                  {date} · {(snap.size_bytes / 1024).toFixed(1)} KB
                </Text>
              </Flex>
              <Button
                size="1"
                variant="soft"
                onClick={() => handleRestore(snap.id)}
                loading={restore.isPending}
                data-testid={`restore-snapshot-btn-${snap.id}`}
              >
                Restaurar
              </Button>
            </Flex>
          );
        })}
      </Flex>
    </Card>
  );
}
