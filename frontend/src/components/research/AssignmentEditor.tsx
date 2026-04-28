import { useState, useMemo } from "react";
import {
  Button,
  Callout,
  Dialog,
  Flex,
  Heading,
  Select,
  Text,
  TextField,
} from "@radix-ui/themes";
import {
  patchResearchAssignments,
  type MapResearchResult,
  type CondadoRename,
  type PatchAssignmentsRequest,
} from "../../api/edit";
import type { ResearchResult } from "../../api/research";
import { useResearchStore } from "../../stores/useResearchStore";

export interface AssignmentEditorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  researchResult: MapResearchResult;
}

type MapCondado = MapResearchResult["condados"][number];

export function AssignmentEditor({
  open,
  onOpenChange,
  projectId,
  researchResult,
}: AssignmentEditorProps) {
  const [draftAssignments, setDraftAssignments] = useState<Record<string, string>>(
    () => ({ ...researchResult.barony_assignments }),
  );
  const [draftCondados, setDraftCondados] = useState<MapCondado[]>(
    () => researchResult.condados.map((c) => ({ ...c })),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function computeDelta(): PatchAssignmentsRequest {
    const ba: Record<string, string> = {};
    for (const [bid, cid] of Object.entries(draftAssignments)) {
      if (researchResult.barony_assignments[bid] !== cid) ba[bid] = cid;
    }
    const cr: Record<string, CondadoRename> = {};
    const original = new Map(researchResult.condados.map((c) => [c.id, c]));
    for (const c of draftCondados) {
      const orig = original.get(c.id);
      if (!orig) continue;
      const rename: CondadoRename = {};
      if (orig.name !== c.name) rename.name = c.name;
      if (orig.duchy_id !== c.duchy_id) rename.duchy_id = c.duchy_id;
      if (Object.keys(rename).length > 0) cr[c.id] = rename;
    }
    const out: PatchAssignmentsRequest = {};
    if (Object.keys(ba).length > 0) out.barony_assignments = ba;
    if (Object.keys(cr).length > 0) out.condado_renames = cr;
    return out;
  }

  const hasChanges = useMemo(() => {
    const delta = computeDelta();
    return (
      Object.keys(delta.barony_assignments ?? {}).length +
        Object.keys(delta.condado_renames ?? {}).length >
      0
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftAssignments, draftCondados]);

  async function handleSave() {
    setSubmitting(true);
    setError(null);
    try {
      const result = await patchResearchAssignments(projectId, computeDelta());
      // Cast: store uses legacy ResearchResult; type unification is a separate quick task.
      useResearchStore.getState().setManualResult(result as unknown as ResearchResult);
      onOpenChange(false);
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      setError(raw.slice(0, 600));
    } finally {
      setSubmitting(false);
    }
  }

  const baronySorted = Object.entries(draftAssignments).sort(([a], [b]) =>
    a.localeCompare(b),
  );

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content style={{ maxWidth: 640 }}>
        <Dialog.Title size="4">Editar assignments</Dialog.Title>

        {/* Section 1 — Barony → Condado assignments */}
        <Flex direction="column" gap="3" mt="4">
          <Heading size="3">Atribuições de baronies</Heading>
          <Flex direction="column" gap="2">
            {baronySorted.map(([bid, cid]) => (
              <Flex key={bid} align="center" gap="3">
                <Text size="2" style={{ minWidth: 80 }}>
                  {bid}
                </Text>
                <Select.Root
                  name={`barony-${bid}`}
                  value={cid}
                  onValueChange={(newCid) =>
                    setDraftAssignments((prev) => ({ ...prev, [bid]: newCid }))
                  }
                >
                  <Select.Trigger data-testid={`barony-row-${bid}`} />
                  <Select.Content>
                    {researchResult.condados.map((c) => (
                      <Select.Item key={c.id} value={c.id}>
                        {c.name} ({c.id})
                      </Select.Item>
                    ))}
                  </Select.Content>
                </Select.Root>
              </Flex>
            ))}
          </Flex>
        </Flex>

        {/* Section 2 — Condado renames */}
        <Flex direction="column" gap="3" mt="4">
          <Heading size="3">Renomear condados</Heading>
          <Flex direction="column" gap="2">
            {draftCondados.map((c) => (
              <Flex key={c.id} align="center" gap="3">
                <TextField.Root
                  value={c.name}
                  data-testid={`condado-name-${c.id}`}
                  style={{ flex: 1 }}
                  onChange={(e) => {
                    const newName = e.target.value;
                    setDraftCondados((prev) =>
                      prev.map((dc) => (dc.id === c.id ? { ...dc, name: newName } : dc)),
                    );
                  }}
                />
                <Select.Root
                  value={c.duchy_id}
                  onValueChange={(newDuchyId) =>
                    setDraftCondados((prev) =>
                      prev.map((dc) =>
                        dc.id === c.id ? { ...dc, duchy_id: newDuchyId } : dc,
                      ),
                    )
                  }
                >
                  <Select.Trigger data-testid={`condado-duchy-${c.id}`} />
                  <Select.Content>
                    {Object.entries(researchResult.duchies).map(([did, duchy]) => (
                      <Select.Item key={did} value={did}>
                        {duchy.name} ({did})
                      </Select.Item>
                    ))}
                  </Select.Content>
                </Select.Root>
              </Flex>
            ))}
          </Flex>
        </Flex>

        {/* Error Callout */}
        {error && (
          <Callout.Root color="red" mt="3" data-testid="error-callout">
            <Callout.Text>{error}</Callout.Text>
          </Callout.Root>
        )}

        {/* Footer */}
        <Flex justify="end" gap="2" mt="4">
          <Button variant="soft" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            color="blue"
            disabled={!hasChanges || submitting}
            data-testid="save-button"
            onClick={handleSave}
          >
            {submitting ? "Salvando…" : "Salvar"}
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
