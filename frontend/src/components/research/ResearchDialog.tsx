import { Badge, Button, Dialog, Flex, Heading, Text, TextArea, TextField } from "@radix-ui/themes";
import { useCachedResultQuery } from "../../api/research";
import { useResearchStream } from "../../hooks/useResearchStream";
import { useResearchStore } from "../../stores/useResearchStore";
import { ProviderSelector } from "./ProviderSelector";
import { AuthSetupSheet } from "./AuthSetupSheet";

interface ResearchDialogProps {
  projectId: string;
}

/**
 * ResearchDialog — Phase 3 main research trigger UI.
 *
 * Sections (per 03-UI-SPEC.md layout contract):
 *   1. Provider + auth row (ProviderSelector + AuthSetupSheet)
 *   2. Country + period inputs
 *   3. Progress / result area (5 states: idle, streaming, cached, success, error)
 *
 * Copy: all strings are in Portuguese (Brazilian) per UI-SPEC Copywriting Contract.
 * Colors: blue CTA, green success badges, amber warnings, red errors — via Radix tokens.
 * Dimensions: max-width 560px (Dialog.Content), Sheet width 400px (in AuthSetupSheet).
 */
export function ResearchDialog({ projectId }: ResearchDialogProps) {
  const dialogOpen = useResearchStore((s) => s.dialogOpen);
  const setDialogOpen = useResearchStore((s) => s.setDialogOpen);
  const selectedProviderId = useResearchStore((s) => s.selectedProviderId);
  const setSelectedProvider = useResearchStore((s) => s.setSelectedProvider);
  const country = useResearchStore((s) => s.country);
  const setCountry = useResearchStore((s) => s.setCountry);
  const periodStart = useResearchStore((s) => s.periodStart);
  const setPeriodStart = useResearchStore((s) => s.setPeriodStart);
  const periodEnd = useResearchStore((s) => s.periodEnd);
  const setPeriodEnd = useResearchStore((s) => s.setPeriodEnd);
  const manualJson = useResearchStore((s) => s.manualJson);
  const setManualJson = useResearchStore((s) => s.setManualJson);

  const stream = useResearchStream(projectId);

  // Query cached result when dialog is open and a provider is selected
  const cachedQuery = useCachedResultQuery(
    projectId,
    selectedProviderId,
    dialogOpen
  );

  const hasCached = cachedQuery.data !== null && cachedQuery.data !== undefined;
  const isMaxRetries = stream.retryNotices.length >= 3 && stream.status === "error";

  const handleRevalidateJson = () => {
    // TODO: wire up to POST /api/projects/{id}/research/validate when available
    // For v1, this is a placeholder per D-29 manual JSON editor requirement
    alert("Revalidar JSON: feature em construção.");
  };

  const renderProgressArea = () => {
    if (stream.status === "streaming") {
      const secs = (stream.elapsedMs / 1000).toFixed(1);
      const dots = ".".repeat((Math.floor(stream.elapsedMs / 500) % 3) + 1);
      const lines = [
        ...stream.messages.map((m) => {
          const t = new Date(m.ts);
          const hh = String(t.getHours()).padStart(2, "0");
          const mm = String(t.getMinutes()).padStart(2, "0");
          const ss = String(t.getSeconds()).padStart(2, "0");
          return `[${hh}:${mm}:${ss}] ${m.text}`;
        }),
        ...stream.retryNotices,
      ];
      return (
        <Flex direction="column" gap="2">
          <Flex align="center" gap="2">
            <Text size="2" color="blue" weight="bold">
              Pesquisando{dots}
            </Text>
            <Text size="1" color="gray">
              {secs}s decorridos
            </Text>
          </Flex>
          <pre
            style={{
              padding: 8,
              background: "#f5f5f5",
              borderRadius: 4,
              maxHeight: 200,
              overflow: "auto",
              fontSize: 11,
              whiteSpace: "pre-wrap",
            }}
          >
            {lines.length > 0 ? lines.join("\n") : (
              <span style={{ color: "#999" }}>
                Aguardando o modelo responder. Modelos locais grandes podem levar 30-120s{dots}
              </span>
            )}
          </pre>
          <Button variant="soft" color="red" onClick={() => stream.cancel()}>
            Cancelar pesquisa
          </Button>
        </Flex>
      );
    }

    if (stream.status === "cancelled") {
      return (
        <Flex direction="column" gap="2">
          <Badge color="gray" size="2">
            Pesquisa cancelada
          </Badge>
          <Text size="2" color="gray">
            Você pode iniciar uma nova pesquisa a qualquer momento.
          </Text>
        </Flex>
      );
    }

    if (stream.status === "success") {
      const r = stream.result;
      return (
        <Flex direction="column" gap="2">
          <Badge color="green" size="2">
            Pesquisa concluída
          </Badge>
          {r && (
            <Text size="2">
              {Object.keys(r.kingdoms).length} reinos ·{" "}
              {Object.keys(r.duchies).length} ducados ·{" "}
              {r.condados_assignment.length} condados ·{" "}
              {Object.keys(r.baronies).length} baronias
            </Text>
          )}
          <Button variant="soft" onClick={() => setDialogOpen(false)}>
            Fechar
          </Button>
        </Flex>
      );
    }

    if (stream.status === "cached" || (stream.status === "idle" && hasCached)) {
      const r = stream.result ?? cachedQuery.data;
      return (
        <Flex direction="column" gap="2">
          <Badge color="green" size="2">
            Resultado em cache
          </Badge>
          {r && (
            <Text size="2">
              {Object.keys(r.kingdoms).length} reinos ·{" "}
              {Object.keys(r.duchies).length} ducados ·{" "}
              {r.condados_assignment.length} condados ·{" "}
              {Object.keys(r.baronies).length} baronias
            </Text>
          )}
          <Button
            variant="soft"
            onClick={() => stream.start(selectedProviderId, true)}
          >
            Forçar nova pesquisa
          </Button>
        </Flex>
      );
    }

    if (stream.status === "error") {
      if (isMaxRetries) {
        return (
          <Flex direction="column" gap="2">
            <Heading size="3" color="red">
              Falha após 3 tentativas
            </Heading>
            <Text size="2">
              O modelo retornou JSON que não passou na validação 3 vezes seguidas.
              Veja os erros de cada tentativa abaixo — o problema costuma ser um
              campo faltando, um tipo errado ou um condado_id inventado.
            </Text>

            {stream.retryNotices.length > 0 && (
              <pre
                style={{
                  padding: 8,
                  background: "#fff5f5",
                  border: "1px solid #fecaca",
                  borderRadius: 4,
                  maxHeight: 160,
                  overflow: "auto",
                  fontSize: 11,
                  whiteSpace: "pre-wrap",
                }}
              >
                {stream.retryNotices.join("\n\n")}
              </pre>
            )}

            {stream.error && (
              <Text size="1" color="red" style={{ whiteSpace: "pre-wrap" }}>
                <strong>Erro final:</strong> {stream.error}
              </Text>
            )}

            <Text size="2" color="gray">
              Opções: tente outro provedor (Claude costuma ser mais confiável com JSON estruturado),
              ou cole/edite um JSON manualmente abaixo:
            </Text>
            <TextArea
              value={manualJson}
              onChange={(e) => setManualJson(e.target.value)}
              placeholder="Cola ou edita o JSON aqui…"
              style={{ minHeight: 120, fontFamily: "monospace", fontSize: 11 }}
            />
            <Button onClick={handleRevalidateJson}>Revalidar JSON</Button>
          </Flex>
        );
      }

      return (
        <Flex direction="column" gap="2">
          <Text size="2" color="red" style={{ whiteSpace: "pre-wrap" }}>
            <strong>Erro ao comunicar com {selectedProviderId}:</strong> {stream.error}
          </Text>
          {stream.retryNotices.length > 0 && (
            <pre
              style={{
                padding: 8,
                background: "#fff5f5",
                border: "1px solid #fecaca",
                borderRadius: 4,
                maxHeight: 120,
                overflow: "auto",
                fontSize: 11,
                whiteSpace: "pre-wrap",
              }}
            >
              {stream.retryNotices.join("\n\n")}
            </pre>
          )}
        </Flex>
      );
    }

    // idle state — no cached result
    return (
      <Flex direction="column" gap="1">
        <Text size="2" weight="bold">
          Nenhuma pesquisa realizada
        </Text>
        <Text size="2" color="gray">
          Seleciona um provedor e inicia a pesquisa para receber a hierarquia política histórica.
        </Text>
      </Flex>
    );
  };

  return (
    <>
      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <Dialog.Content style={{ maxWidth: 560 }}>
          <Dialog.Title size="4">Pesquisa histórica com LLM</Dialog.Title>

          {/* Section 1 — Provider selection */}
          <Flex direction="column" gap="3" mt="4">
            <Heading size="3">Provedor LLM</Heading>
            <ProviderSelector
              value={selectedProviderId}
              onChange={setSelectedProvider}
            />
          </Flex>

          {/* Section 2 — Research inputs */}
          <Flex direction="column" gap="3" mt="4">
            <Flex direction="column" gap="1">
              <Text size="2" weight="bold">
                País (QID Wikidata)
              </Text>
              <TextField.Root
                placeholder="Ex.: Q29 (Espanha) ou Q29,Q45 para vários"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
              />
              <Text size="1" color="gray">
                Use vírgula para múltiplos países — ex.: Q29,Q45 para Península Ibérica
              </Text>
            </Flex>

            <Flex gap="3" align="end">
              <Flex direction="column" gap="1" style={{ flex: 1 }}>
                <Text size="2" weight="bold">
                  Início do período
                </Text>
                <Flex align="center" gap="1">
                  <TextField.Root
                    type="number"
                    value={String(periodStart)}
                    onChange={(e) => setPeriodStart(Number(e.target.value))}
                    style={{ flex: 1 }}
                  />
                  <Text size="2" color="gray">
                    d.C.
                  </Text>
                </Flex>
              </Flex>

              <Flex direction="column" gap="1" style={{ flex: 1 }}>
                <Text size="2" weight="bold">
                  Fim do período
                </Text>
                <Flex align="center" gap="1">
                  <TextField.Root
                    type="number"
                    value={String(periodEnd)}
                    onChange={(e) => setPeriodEnd(Number(e.target.value))}
                    style={{ flex: 1 }}
                  />
                  <Text size="2" color="gray">
                    d.C.
                  </Text>
                </Flex>
              </Flex>
            </Flex>
          </Flex>

          {/* Section 3 — Progress / result area */}
          <Flex direction="column" gap="2" mt="4">
            {renderProgressArea()}
          </Flex>

          {/* Footer */}
          <Flex justify="end" gap="2" mt="4">
            <Dialog.Close>
              <Button variant="soft">Cancelar</Button>
            </Dialog.Close>
            <Button
              color="blue"
              disabled={stream.status === "streaming"}
              onClick={() => stream.start(selectedProviderId, false)}
            >
              {stream.status === "streaming" ? "Pesquisando…" : "Iniciar pesquisa"}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>

      {/* AuthSetupSheet is mounted outside the Dialog to avoid z-index conflicts */}
      <AuthSetupSheet />
    </>
  );
}
