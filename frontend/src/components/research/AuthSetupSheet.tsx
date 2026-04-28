import { useState } from "react";
import {
  AlertDialog,
  Badge,
  Button,
  Dialog,
  Flex,
  Heading,
  Select,
  Text,
  TextField,
} from "@radix-ui/themes";
import {
  useProvidersQuery,
  useStoreCredentialMutation,
  useClearCredentialMutation,
  useOAuthStartMutation,
  useOllamaModelsQuery,
  useSetOllamaModelMutation,
  probeLlamacppServer,
} from "../../api/research";
import { useResearchStore } from "../../stores/useResearchStore";

/**
 * AuthSetupSheet — a right-side panel (simulated as a positioned Dialog) for
 * configuring per-provider authentication credentials.
 *
 * Radix Themes 3.x does not export a native Sheet component. We use
 * Dialog.Content with CSS overrides to position it as a right-side panel:
 * position: fixed, right: 0, top: 0, height: 100vh, width: 400px.
 * This is the documented approximation per 03-UI-SPEC.md.
 *
 * Security (T-3-14): The API key value is held only in local React state
 * (apiKey useState) and submitted directly via useStoreCredentialMutation.
 * It is NEVER stored in useResearchStore or any Zustand store, ensuring
 * credentials are not accessible to the broader application state.
 */
export function AuthSetupSheet() {
  const sheetOpenForProvider = useResearchStore((s) => s.sheetOpenForProvider);
  const closeSheet = useResearchStore((s) => s.closeSheet);
  const { data: providers } = useProvidersQuery();
  const storeCred = useStoreCredentialMutation();
  const clearCred = useClearCredentialMutation();
  const oauthStart = useOAuthStartMutation();

  // Local state — API key stays here, never in Zustand store (T-3-14)
  const [apiKey, setApiKey] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [clearDialogOpen, setClearDialogOpen] = useState(false);

  const isOpen = sheetOpenForProvider !== null;
  const providerId = sheetOpenForProvider ?? "";

  const provider = providers?.find((p) => p.provider_id === providerId);

  const handleClose = () => {
    setApiKey("");
    setSaveSuccess(false);
    closeSheet();
  };

  const handleSaveKey = async () => {
    if (!apiKey.trim() || !providerId) return;
    await storeCred.mutateAsync({ provider: providerId, api_key: apiKey });
    setSaveSuccess(true);
    setApiKey("");
  };

  const handleOAuthStart = async () => {
    if (!providerId) return;
    const result = await oauthStart.mutateAsync(providerId);
    window.open(result.authorize_url, "_blank");
  };

  const handleClearCreds = async () => {
    if (!providerId) return;
    await clearCred.mutateAsync(providerId);
    setClearDialogOpen(false);
    handleClose();
  };

  const isClaudeWithCli =
    provider?.provider_id === "claude" &&
    provider.auth_methods.some((m) => m.type === "cli") &&
    provider.configured === true;

  const isGemini = provider?.provider_id === "gemini";
  const isOllama = provider?.provider_id === "ollama";
  const isLlamacpp = provider?.provider_id === "llamacpp";

  // Llama.cpp local panel state (Etapa 5 — quick-260428-fjc)
  const [llamacppBaseUrl, setLlamacppBaseUrl] = useState("http://localhost:8080");
  const [llamacppHealth, setLlamacppHealth] = useState<
    { healthy: boolean; message: string } | null
  >(null);
  const [llamacppTesting, setLlamacppTesting] = useState(false);

  const handleTestLlamacpp = async () => {
    setLlamacppTesting(true);
    try {
      // Reuses probeLlamacppServer from api/research.ts — no new backend endpoint.
      const result = await probeLlamacppServer(llamacppBaseUrl);
      setLlamacppHealth(result);
    } finally {
      setLlamacppTesting(false);
    }
  };

  const ollamaModels = useOllamaModelsQuery(isOllama && isOpen);
  const setOllamaModel = useSetOllamaModelMutation();
  const [pickedOllamaModel, setPickedOllamaModel] = useState<string>("");

  const activeOllamaModel =
    pickedOllamaModel ||
    ollamaModels.data?.selected ||
    ollamaModels.data?.models[0] ||
    "";

  const handleSaveOllamaModel = async () => {
    if (!activeOllamaModel) return;
    await setOllamaModel.mutateAsync(activeOllamaModel);
    setSaveSuccess(true);
  };

  return (
    <>
      {/* Right-side Sheet implemented via Dialog.Content with CSS overrides */}
      <Dialog.Root open={isOpen} onOpenChange={(open) => { if (!open) handleClose(); }}>
        <Dialog.Content
          style={{
            position: "fixed",
            right: 0,
            top: 0,
            height: "100vh",
            width: 400,
            maxWidth: 400,
            borderRadius: 0,
            margin: 0,
            padding: 24,
            overflowY: "auto",
          }}
        >
          <Dialog.Title>
            Configurar {provider?.display_name ?? providerId}
          </Dialog.Title>

          <Flex direction="column" gap="4" mt="4">
            {/* CLI badge — only for Claude when CLI auth is configured */}
            {isClaudeWithCli && (
              <Badge color="green" size="2">
                CLI detectado — token válido
              </Badge>
            )}

            {/* Persistent status badge — shows whether the provider has a credential saved */}
            {!isOllama && !isLlamacpp && !isClaudeWithCli && provider && (
              <Badge color={provider.configured ? "green" : "amber"} size="2">
                {provider.configured
                  ? "✓ Credencial salva nesta sessão"
                  : "⚠ Nenhuma credencial configurada"}
              </Badge>
            )}

            {/* OAuth button — only for Gemini */}
            {isGemini && (
              <Flex direction="column" gap="2">
                <Button
                  variant="soft"
                  color="blue"
                  onClick={handleOAuthStart}
                  disabled={oauthStart.isPending}
                >
                  {oauthStart.isPending ? "Redirecionando…" : "Entrar com o Google"}
                </Button>
                {oauthStart.isError && (
                  <Text size="1" color="red">
                    Falha no login Google
                  </Text>
                )}
              </Flex>
            )}

            {/* Ollama: model picker instead of API key */}
            {isOllama && (
              <Flex direction="column" gap="2">
                <Heading size="3">Modelo local (Ollama)</Heading>
                <Text size="1" color="gray">
                  Ollama roda localmente e não precisa de chave de API. Escolha um dos modelos que você já baixou com <code>ollama pull</code>.
                </Text>
                {ollamaModels.isLoading && (
                  <Text size="2" color="gray">Detectando modelos...</Text>
                )}
                {ollamaModels.data && !ollamaModels.data.healthy && (
                  <Text size="2" color="red">
                    {ollamaModels.data.message ?? "Ollama indisponível."}
                  </Text>
                )}
                {ollamaModels.data && ollamaModels.data.healthy && ollamaModels.data.models.length === 0 && (
                  <Text size="2" color="amber">
                    Nenhum modelo encontrado. Rode <code>ollama pull qwen2.5</code> (ou outro) e recarrega.
                  </Text>
                )}
                {ollamaModels.data && ollamaModels.data.models.length > 0 && (
                  <>
                    <Select.Root
                      value={activeOllamaModel}
                      onValueChange={(v) => {
                        setPickedOllamaModel(v);
                        setSaveSuccess(false);
                      }}
                    >
                      <Select.Trigger placeholder="Escolhe um modelo..." />
                      <Select.Content>
                        {ollamaModels.data.models.map((m) => (
                          <Select.Item key={m} value={m}>
                            {m}
                          </Select.Item>
                        ))}
                      </Select.Content>
                    </Select.Root>
                    {ollamaModels.data.selected && (
                      <Text size="1" color="gray">
                        Modelo ativo: <strong>{ollamaModels.data.selected}</strong>
                      </Text>
                    )}
                    {saveSuccess && (
                      <Text size="1" color="green">Modelo selecionado com sucesso.</Text>
                    )}
                    <Button
                      onClick={handleSaveOllamaModel}
                      disabled={!activeOllamaModel || setOllamaModel.isPending}
                      color="blue"
                    >
                      {setOllamaModel.isPending ? "Salvando..." : "Usar este modelo"}
                    </Button>
                  </>
                )}
              </Flex>
            )}

            {/* Llama.cpp local panel — base_url + Testar conexão + status badge */}
            {isLlamacpp && (
              <Flex direction="column" gap="2">
                <Heading size="3">Servidor Llama.cpp local</Heading>
                <Text size="1" color="gray">
                  Llama.cpp roda localmente e não precisa de chave de API. Informa a URL do servidor (default: http://localhost:8080) e testa a conexão.
                </Text>
                <TextField.Root
                  placeholder="http://localhost:8080"
                  value={llamacppBaseUrl}
                  onChange={(e) => {
                    setLlamacppBaseUrl(e.target.value);
                    setLlamacppHealth(null);
                  }}
                />
                <Button
                  onClick={handleTestLlamacpp}
                  disabled={!llamacppBaseUrl.trim() || llamacppTesting}
                  color="blue"
                >
                  {llamacppTesting ? "Testando..." : "Testar conexão"}
                </Button>
                {llamacppHealth && (
                  <Badge color={llamacppHealth.healthy ? "green" : "red"} size="2">
                    {llamacppHealth.healthy
                      ? `✓ ${llamacppHealth.message}`
                      : `✗ ${llamacppHealth.message}`}
                  </Badge>
                )}
                <Text size="1" color="gray">
                  O modelo é definido pelo próprio servidor (parâmetro de boot do llama-server). Não há seleção de modelo aqui.
                </Text>
              </Flex>
            )}

            {/* API key input — hidden for Ollama and Llama.cpp (local, no auth) */}
            {!isOllama && !isLlamacpp && (
              <Flex direction="column" gap="2">
                <Heading size="3">Chave de API</Heading>
                <TextField.Root
                  type="password"
                  placeholder="Cola a chave aqui (apenas nesta sessão)"
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.target.value);
                    setSaveSuccess(false);
                  }}
                />
                {saveSuccess && (
                  <Text size="1" color="green">
                    Chave salva com sucesso.
                  </Text>
                )}
                {storeCred.isError && (
                  <Text size="1" color="red">
                    Erro ao salvar chave: {(storeCred.error as Error).message}
                  </Text>
                )}
                <Button
                  onClick={handleSaveKey}
                  disabled={!apiKey.trim() || storeCred.isPending}
                  color="blue"
                >
                  {storeCred.isPending ? "Salvando..." : "Usar esta chave"}
                </Button>
              </Flex>
            )}

            {/* Destructive clear credentials — at the bottom */}
            <Flex mt="auto" pt="4" style={{ borderTop: "1px solid var(--gray-4)" }}>
              <Button
                variant="soft"
                color="red"
                onClick={() => setClearDialogOpen(true)}
              >
                Limpar credenciais
              </Button>
            </Flex>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>

      {/* Confirmation AlertDialog for destructive "Limpar credenciais" action */}
      <AlertDialog.Root open={clearDialogOpen} onOpenChange={setClearDialogOpen}>
        <AlertDialog.Content maxWidth="400px">
          <AlertDialog.Title>Limpar credenciais?</AlertDialog.Title>
          <AlertDialog.Description size="2">
            As credenciais serão removidas desta sessão. Precisarás configurá-las novamente.
          </AlertDialog.Description>
          <Flex gap="3" mt="4" justify="end">
            <AlertDialog.Cancel>
              <Button variant="soft" color="gray">
                Cancelar
              </Button>
            </AlertDialog.Cancel>
            <AlertDialog.Action>
              <Button
                variant="solid"
                color="red"
                onClick={handleClearCreds}
                disabled={clearCred.isPending}
              >
                {clearCred.isPending ? "Limpando…" : "Limpar"}
              </Button>
            </AlertDialog.Action>
          </Flex>
        </AlertDialog.Content>
      </AlertDialog.Root>
    </>
  );
}
