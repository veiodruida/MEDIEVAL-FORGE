import { useState } from "react";
import {
  AlertDialog,
  Badge,
  Button,
  Dialog,
  Flex,
  Heading,
  Text,
  TextField,
} from "@radix-ui/themes";
import {
  useProvidersQuery,
  useStoreCredentialMutation,
  useClearCredentialMutation,
  useOAuthStartMutation,
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

            {/* API key input — always shown */}
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
                {storeCred.isPending ? "Salvando…" : "Usar esta chave"}
              </Button>
            </Flex>

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
