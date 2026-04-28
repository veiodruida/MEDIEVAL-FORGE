import { useState } from "react";
import { Tabs, Box, Text, Flex, Button, Heading, Badge, ScrollArea } from "@radix-ui/themes";
import ReactMarkdown from "react-markdown";
import { useQuery } from "@tanstack/react-query";
import { useCodexStream } from "../../hooks/useCodexStream";
import {
  CODEX_CATEGORY_KEYS,
  CODEX_CATEGORY_LABELS,
  fetchCachedCodex,
  type CodexResult,
  type CodexCategoryKey,
} from "../../api/codex";
import { ProviderSelector } from "../research/ProviderSelector";

interface CodexViewerProps {
  projectId: string;
}

export function CodexViewer({ projectId }: CodexViewerProps) {
  const [providerId, setProviderId] = useState<string>("claude");
  const stream = useCodexStream(projectId);

  const cachedQuery = useQuery<CodexResult | null>({
    queryKey: ["codex", "cached", projectId, providerId],
    queryFn: () => fetchCachedCodex(projectId, providerId),
  });

  const result: CodexResult | null = stream.result ?? cachedQuery.data ?? null;

  const isStreaming = stream.status === "streaming";
  const hasError = stream.status === "error";
  const hasCachedResult = cachedQuery.data != null && stream.result == null;

  return (
    <Box p="4">
      {/* Header: provider picker + Gerar Codex button + status badge */}
      <Flex direction="column" gap="3" mb="4">
        <Heading size="4">Codex Medieval</Heading>

        <ProviderSelector value={providerId} onChange={setProviderId} />

        <Flex align="center" gap="3">
          <Button
            onClick={() => stream.start(providerId, false)}
            disabled={isStreaming}
          >
            {isStreaming ? "Gerando…" : "Gerar Codex"}
          </Button>

          {isStreaming && (
            <Badge color="blue">
              Gerando… ({Math.floor(stream.elapsedMs / 1000)}s)
            </Badge>
          )}

          {stream.status === "success" && (
            <Badge color="green">Codex gerado</Badge>
          )}

          {stream.status === "cached" && (
            <Badge color="amber">Resultado em cache</Badge>
          )}

          {hasCachedResult && stream.status === "idle" && (
            <Badge color="amber">Cache disponível</Badge>
          )}
        </Flex>

        {/* Streaming log */}
        {isStreaming && stream.messages.length > 0 && (
          <ScrollArea style={{ maxHeight: "120px" }}>
            <Box p="2" style={{ background: "var(--gray-2)", borderRadius: "4px" }}>
              {stream.messages.map((msg, i) => (
                <Text key={i} size="1" color="gray" as="p">
                  {msg.text}
                </Text>
              ))}
            </Box>
          </ScrollArea>
        )}

        {/* Retry notices */}
        {stream.retryNotices.length > 0 && (
          <Box>
            {stream.retryNotices.map((notice, i) => (
              <Text key={i} size="1" color="amber" as="p">
                {notice}
              </Text>
            ))}
          </Box>
        )}

        {/* Error state */}
        {hasError && stream.error && (
          <Box p="3" style={{ background: "var(--red-2)", borderRadius: "4px" }}>
            <Text color="red">{stream.error}</Text>
          </Box>
        )}
      </Flex>

      {/* Tabs — only rendered when result is available */}
      {result != null ? (
        <Tabs.Root defaultValue={CODEX_CATEGORY_KEYS[0]}>
          <Tabs.List>
            {CODEX_CATEGORY_KEYS.map((key: CodexCategoryKey) => (
              <Tabs.Trigger
                key={key}
                value={key}
                data-testid={`codex-tab-${key}`}
              >
                {CODEX_CATEGORY_LABELS[key]}
              </Tabs.Trigger>
            ))}
          </Tabs.List>

          {CODEX_CATEGORY_KEYS.map((key: CodexCategoryKey) => {
            const category = result[key];
            return (
              <Tabs.Content key={key} value={key}>
                <Box pt="3">
                  {category.summary && (
                    <Text size="2" color="gray" mb="3" as="p">
                      {category.summary}
                    </Text>
                  )}

                  {category.entries.length === 0 ? (
                    <Text color="gray">Nenhuma entrada nesta categoria</Text>
                  ) : (
                    <Flex direction="column" gap="4">
                      {category.entries.map((entry) => (
                        <Box key={entry.id}>
                          <Heading size="3" mb="1">
                            {entry.name}
                          </Heading>
                          <ReactMarkdown>{entry.description}</ReactMarkdown>
                        </Box>
                      ))}
                    </Flex>
                  )}
                </Box>
              </Tabs.Content>
            );
          })}
        </Tabs.Root>
      ) : (
        !hasError && !isStreaming && (
          <Text color="gray" size="2">
            Clique em "Gerar Codex" para criar o codex histórico deste projeto.
          </Text>
        )
      )}
    </Box>
  );
}
