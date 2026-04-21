import { Badge, Flex, RadioGroup, Text, Tooltip } from "@radix-ui/themes";
import { useProvidersQuery, useHealthQuery, type Provider, type AuthMethod } from "../../api/research";
import { useResearchStore } from "../../stores/useResearchStore";

/**
 * Derives the auth status badge text for a provider.
 *
 * The /api/llm/providers endpoint does not currently return which specific
 * auth method was used — it only returns `configured: boolean` and the list
 * of available auth_methods in priority order. For v1, we infer the method
 * that was most likely used from the auth_methods array:
 *   - If any method is type "cli" → assume CLI was used (Claude typically)
 *   - If any method is type "oauth" → assume OAuth was used (Gemini typically)
 *   - If any method is type "api_key" with env_var → assume env var was used
 *   - Otherwise → assume session key (pasted in dialog)
 *
 * This approximation is intentional and documented here. A future API version
 * should return `used_method` to eliminate the inference.
 */
function badgeText(provider: Provider): string {
  if (!provider.configured) return "⚠ Configuração necessária";

  const methods: AuthMethod[] = provider.auth_methods;

  const hasCli = methods.some((m) => m.type === "cli");
  if (hasCli) return "✓ via CLI (claude)";

  const hasOAuth = methods.some((m) => m.type === "oauth");
  if (hasOAuth) return "✓ via OAuth (Google)";

  const hasEnvVar = methods.some(
    (m) => m.type === "api_key" && (m as { type: "api_key"; env_var: string | null }).env_var !== null
  );
  if (hasEnvVar) return "✓ via variável de ambiente";

  return "✓ via chave de sessão";
}

interface ProviderSelectorProps {
  value: string;
  onChange: (providerId: string) => void;
}

export function ProviderSelector({ value, onChange }: ProviderSelectorProps) {
  const { data: providers, isLoading: providersLoading } = useProvidersQuery();
  const { data: health } = useHealthQuery();
  const openSheet = useResearchStore((s) => s.openSheet);

  if (providersLoading) {
    return (
      <Text size="2" color="gray">
        Carregando provedores…
      </Text>
    );
  }

  if (!providers || providers.length === 0) {
    return (
      <Text size="2" color="gray">
        Nenhum provedor disponível.
      </Text>
    );
  }

  return (
    <RadioGroup.Root value={value} onValueChange={onChange}>
      <Flex direction="column" gap="2">
        {providers.map((p) => {
          const ollamaUnhealthy =
            p.provider_id === "ollama" &&
            health !== undefined &&
            health["ollama"] !== undefined &&
            !health["ollama"].healthy;

          const radioItem = (
            <Flex key={p.provider_id} align="center" gap="2">
              <RadioGroup.Item
                value={p.provider_id}
                disabled={ollamaUnhealthy}
              />
              <Flex direction="column" gap="1" style={{ flex: 1 }}>
                <Text size="2">{p.display_name}</Text>
                <Flex align="center" gap="2">
                  <Badge color={p.configured ? "green" : "amber"} size="1">
                    {badgeText(p)}
                  </Badge>
                  {/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
                  <Text
                    size="1"
                    color="blue"
                    style={{ cursor: "pointer", textDecoration: "underline" }}
                    onClick={() => openSheet(p.provider_id)}
                  >
                    Configurar
                  </Text>
                </Flex>
              </Flex>
            </Flex>
          );

          if (ollamaUnhealthy) {
            return (
              <Tooltip
                key={p.provider_id}
                content="Inicia `ollama serve` e executa `ollama pull qwen2.5` para usar LLM local."
              >
                {radioItem}
              </Tooltip>
            );
          }

          return radioItem;
        })}
      </Flex>
    </RadioGroup.Root>
  );
}
