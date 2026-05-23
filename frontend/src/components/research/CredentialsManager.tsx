/**
 * CredentialsManager dialog (UAT 2026-05-23).
 *
 * Lets the user paste / drop a `.env` to bulk-import API keys, or set
 * them one at a time. Each provider row carries a "fonte" badge:
 *   - db    → key set via this UI (or a previous .env import)
 *   - env   → backend process env carries the key (read-only here)
 *   - none  → no key resolvable; user must paste one
 *
 * Keys are write-only — the GET endpoint never returns them — so a user
 * who forgot what they pasted must paste it again. Acceptable trade-off:
 * the alternative is logging key material in our DB log lines.
 */
import { useMemo, useRef, useState } from 'react'
import {
  Badge,
  Box,
  Button,
  Callout,
  Dialog,
  Flex,
  Separator,
  Text,
  TextField,
} from '@radix-ui/themes'
import {
  CheckCircledIcon,
  ExclamationTriangleIcon,
  TrashIcon,
} from '@radix-ui/react-icons'
import {
  useCredentials,
  useDeleteCredential,
  useDiscoverDotenv,
  useImportDotenv,
  useSetCredential,
  type DiscoverResult,
  type ImportResult,
} from '../../api/useCredentials'

export interface CredentialsManagerProps {
  open: boolean
  onOpenChange: (next: boolean) => void
}

function sourceBadge(source: 'db' | 'env' | 'none') {
  if (source === 'db') return <Badge color="green" variant="soft">Configurada (DB)</Badge>
  if (source === 'env') return <Badge color="blue" variant="soft">Configurada (env)</Badge>
  return <Badge color="gray" variant="soft">Não configurada</Badge>
}

export function CredentialsManager({ open, onOpenChange }: CredentialsManagerProps) {
  const list = useCredentials(open)
  const setCred = useSetCredential()
  const delCred = useDeleteCredential()
  const importEnv = useImportDotenv()
  const discoverEnv = useDiscoverDotenv()

  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({})
  const [envText, setEnvText] = useState('')
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [discoverResult, setDiscoverResult] = useState<DiscoverResult | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const rows = useMemo(
    () => (list.data ?? []).filter((r) => r.accepts_api_key),
    [list.data],
  )

  const handleFile = async (file: File | null) => {
    if (!file) return
    const text = await file.text()
    setEnvText(text)
  }

  const handleImport = () => {
    if (!envText.trim()) return
    importEnv.mutate(
      { text: envText },
      {
        onSuccess: (res) => {
          setImportResult(res)
          setDraftKeys({})
          setEnvText('')
        },
      },
    )
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content style={{ maxWidth: 640 }} data-testid="credentials-manager">
        <Dialog.Title>Chaves de API</Dialog.Title>
        <Dialog.Description>
          <Text size="2" color="gray">
            Configure os provedores de LLM em nuvem. Você pode colar cada chave
            individualmente OU importar um arquivo <code>.env</code> com várias
            chaves de uma só vez. As chaves ficam salvas localmente em
            <code> ~/.medieval-forge/medieval_forge.db</code> e nunca são
            enviadas a terceiros.
          </Text>
        </Dialog.Description>

        <Box mt="4">
          <Text size="2" weight="medium">Buscar .env automaticamente</Text>
          <Flex direction="column" gap="2" mt="1">
            <Text size="1" color="gray">
              Procura por <code>~/.env</code>, <code>~/.medieval-forge/.env</code>
              {' '}e <code>./.env</code>. As chaves encontradas são importadas
              SEM sobrescrever valores que você já salvou via UI.
            </Text>
            <Flex gap="2" align="center">
              <Button
                type="button"
                onClick={() =>
                  discoverEnv.mutate(undefined, {
                    onSuccess: (res) => setDiscoverResult(res),
                  })
                }
                disabled={discoverEnv.isPending}
                data-testid="credentials-discover-button"
              >
                {discoverEnv.isPending ? 'Buscando…' : 'Buscar .env do sistema'}
              </Button>
              {discoverEnv.isError && (
                <Text size="2" color="red">
                  {discoverEnv.error?.message ?? 'Falha ao buscar.'}
                </Text>
              )}
            </Flex>
            {discoverResult && (
              <Callout.Root
                color={discoverResult.imported.length > 0 ? 'green' : 'gray'}
                mt="2"
              >
                <Callout.Icon>
                  <CheckCircledIcon />
                </Callout.Icon>
                <Callout.Text>
                  {discoverResult.imported.length > 0 ? (
                    <>
                      Importadas {discoverResult.imported.length} chave
                      {discoverResult.imported.length === 1 ? '' : 's'}:{' '}
                      {discoverResult.imported.join(', ')}.
                      {discoverResult.paths_with_keys.length > 0 && (
                        <>
                          {' '}Origem: {discoverResult.paths_with_keys.join(', ')}.
                        </>
                      )}
                    </>
                  ) : (
                    <>
                      Nenhuma chave nova encontrada. Caminhos verificados:{' '}
                      {discoverResult.paths_checked.join(', ')}.
                    </>
                  )}
                </Callout.Text>
              </Callout.Root>
            )}
          </Flex>
        </Box>

        <Separator size="4" my="4" />

        <Box>
          <Text size="2" weight="medium">Importar .env manualmente</Text>
          <Flex direction="column" gap="2" mt="1">
            <Flex gap="2" align="center">
              <input
                ref={fileRef}
                type="file"
                accept=".env,text/plain"
                onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
                data-testid="credentials-env-file"
                style={{ fontSize: 12 }}
              />
              {envText && (
                <Text size="1" color="gray">
                  {envText.split('\n').length} linhas carregadas
                </Text>
              )}
            </Flex>
            <textarea
              data-testid="credentials-env-text"
              value={envText}
              onChange={(e) => setEnvText(e.target.value)}
              placeholder="Cole o conteúdo do .env aqui (ex.: ANTHROPIC_API_KEY=...)"
              rows={4}
              style={{
                fontFamily: 'ui-monospace, monospace',
                fontSize: 12,
                padding: 8,
                border: '1px solid var(--gray-6)',
                borderRadius: 6,
                background: 'var(--gray-1)',
              }}
            />
            <Flex gap="2">
              <Button
                type="button"
                onClick={handleImport}
                disabled={!envText.trim() || importEnv.isPending}
                data-testid="credentials-import-button"
              >
                {importEnv.isPending ? 'Importando…' : 'Importar chaves'}
              </Button>
              {importEnv.isError && (
                <Text size="2" color="red">
                  {importEnv.error?.message ?? 'Falha ao importar.'}
                </Text>
              )}
            </Flex>
            {importResult && (
              <Callout.Root color="green" mt="2">
                <Callout.Icon>
                  <CheckCircledIcon />
                </Callout.Icon>
                <Callout.Text>
                  <strong>{importResult.imported.length}</strong> chave
                  {importResult.imported.length === 1 ? '' : 's'} importada
                  {importResult.imported.length === 1 ? '' : 's'}
                  {importResult.imported.length > 0 && (
                    <>: {importResult.imported.join(', ')}.</>
                  )}
                  {importResult.skipped.length > 0 && (
                    <>
                      {' '}Ignoradas (variáveis desconhecidas):{' '}
                      {importResult.skipped.join(', ')}.
                    </>
                  )}
                </Callout.Text>
              </Callout.Root>
            )}
          </Flex>
        </Box>

        <Separator size="4" my="4" />

        <Box>
          <Text size="2" weight="medium">Chaves por provedor</Text>
          {list.isLoading && (
            <Text size="2" color="gray" mt="1" as="p">
              Carregando…
            </Text>
          )}
          {!list.isLoading && rows.length === 0 && (
            <Text size="2" color="gray" mt="1" as="p">
              Nenhum provedor que aceita API key registrado.
            </Text>
          )}
          <Flex direction="column" gap="3" mt="2">
            {rows.map((row) => {
              const draft = draftKeys[row.provider_id] ?? ''
              return (
                <Box
                  key={row.provider_id}
                  data-testid={`credential-row-${row.provider_id}`}
                  style={{
                    border: '1px solid var(--gray-6)',
                    borderRadius: 6,
                    padding: 10,
                  }}
                >
                  <Flex align="center" justify="between" gap="2">
                    <Flex direction="column">
                      <Text size="2" weight="medium">
                        {row.display_name}
                      </Text>
                      {row.env_var && (
                        <Text size="1" color="gray">
                          env: <code>{row.env_var}</code>
                        </Text>
                      )}
                    </Flex>
                    {sourceBadge(row.source)}
                  </Flex>
                  <Flex gap="2" mt="2" align="center">
                    <Box style={{ flex: 1 }}>
                      <TextField.Root
                        type="password"
                        placeholder={
                          row.source === 'env'
                            ? 'Sobrescrever a chave do ambiente…'
                            : 'Cole sua chave aqui'
                        }
                        value={draft}
                        onChange={(e) =>
                          setDraftKeys((prev) => ({
                            ...prev,
                            [row.provider_id]: e.target.value,
                          }))
                        }
                        data-testid={`credential-input-${row.provider_id}`}
                      />
                    </Box>
                    <Button
                      type="button"
                      onClick={() =>
                        setCred.mutate(
                          { providerId: row.provider_id, key: draft },
                          {
                            onSuccess: () =>
                              setDraftKeys((prev) => ({
                                ...prev,
                                [row.provider_id]: '',
                              })),
                          },
                        )
                      }
                      disabled={draft.length < 4 || setCred.isPending}
                      data-testid={`credential-save-${row.provider_id}`}
                    >
                      Salvar
                    </Button>
                    {row.source === 'db' && (
                      <Button
                        type="button"
                        color="red"
                        variant="soft"
                        onClick={() =>
                          delCred.mutate({ providerId: row.provider_id })
                        }
                        disabled={delCred.isPending}
                        data-testid={`credential-delete-${row.provider_id}`}
                      >
                        <TrashIcon /> Remover
                      </Button>
                    )}
                  </Flex>
                </Box>
              )
            })}
          </Flex>
        </Box>

        {(setCred.isError || delCred.isError) && (
          <Callout.Root color="red" mt="3">
            <Callout.Icon>
              <ExclamationTriangleIcon />
            </Callout.Icon>
            <Callout.Text>
              {setCred.error?.message ?? delCred.error?.message ?? 'Falha.'}
            </Callout.Text>
          </Callout.Root>
        )}

        <Flex justify="end" mt="4">
          <Button variant="soft" onClick={() => onOpenChange(false)}>
            Fechar
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  )
}
