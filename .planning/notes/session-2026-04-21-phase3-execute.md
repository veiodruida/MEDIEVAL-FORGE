---
date: 2026-04-21
phase: 03-llm-research-integration
kind: session-report
---

# Sessão — Executar Fase 3 + gap-closure pós-checkpoint

## Estado final

**Fase 3 — executada e verificada manualmente**
- 4 planos completos com SUMMARY.md: 03-01 (LLM adapters), 03-02 (auth), 03-03 (research runner + cache), 03-04 (UI)
- 16 commits de gap-closure corrigindo regressões do agente 03-04 + bugs descobertos no smoke test
- Interface funcional; bloqueada apenas por limitações externas (hardware local pra modelos grandes, quotas de API em conta Pro de provedores)

## O que foi construído

### Backend
- `services/llm/` — Protocol + 4 provider adapters (Claude, OpenAI, Gemini, Ollama) + retry loop de 3 tentativas
- `services/llm/auth.py` — chain de resolução: session → env → CLI piggyback (Claude)
- `services/llm/prompt.py` — prompt com exemplo concreto + regras explícitas (negative examples)
- `services/llm/schemas.py` — ResearchResult + `parse_research_json()` leniente (strip de keys extras)
- `services/research_runner.py` — orquestração SSE: carrega condados → prompt → cache → retry → validate
- `services/research_cache.py` — SHA-256 cache key + SQLite
- `services/credential_store.py` — persistência de credenciais LLM na DB (nova tabela `llm_credentials`)
- `api/auth.py` — 4 endpoints (store/clear credenciais + OAuth start/callback)
- `api/research.py` — POST SSE + GET cached
- `api/llm.py` — GET providers + GET health + GET/POST ollama/models

### Frontend
- `api/research.ts` — TanStack Query hooks pra todos endpoints
- `hooks/useResearchStream.ts` — consumidor SSE com status idle/streaming/cached/success/error/cancelled + elapsedMs
- `stores/useResearchStore.ts` — Zustand com `openDialog(init)` pra pré-popular campos
- `components/research/` — ResearchDialog (560px), ProviderSelector, AuthSetupSheet (sheet 400px)

## Regressões do agente 03-04 (lessons)

O agente de execução do plano 03-04 fez um soft-reset que deletou arquivos de Waves 1 e 2 já merged no main, e ao "restaurar" esqueceu:
- `models.py` — a classe `ResearchCache` inteira
- `main.py` — routers auth/research/llm + init `app.state.credentials` + `Base.metadata.create_all`
- Outros arquivos backend que estavam em commits anteriores

**Aprendizado:** quando um agente GSD diz "restaurei arquivos após reset --soft", verificar `git show --stat` desse commit antes de confiar. Comparar com o commit que originalmente criou esses arquivos.

## Bugs descobertos no smoke test e corrigidos

| # | Sintoma | Causa | Commit |
|---|---------|-------|--------|
| 1 | "Nenhum provedor disponível" | Routers não registrados no main.py | ea6755b |
| 2 | `ImportError: ResearchCache` | Modelo perdido na regressão | a442bc4 |
| 3 | "territories.geojson not found in out/" | Path errado (é `generated/`, não `out/`) | e6b5d61 |
| 4 | Ollama travava em "Aguardando" | Health check sem timeout | dcf36f7 |
| 5 | Campo país fixo em Q29 | Store tinha default hardcoded, não lia do projeto | dcf36f7 |
| 6 | "Ollama: qwen2.5:7b not found" | Modelo hardcoded em vez de descobrir locais | 18901da |
| 7 | "Configurar" do Ollama pedia API key | UX errada pra provider sem auth | 18901da |
| 8 | Usuário não via progresso | SSE sem heartbeat + dialog sem timestamps | 1469220 |
| 9 | Sem botão cancelar | AbortController existia mas UI não expunha | 1469220 |
| 10 | Chave não "ficava salva" visualmente | Badge usava useState local (zerava) | 1469220 |
| 11 | Gemini: "additionalProperties is not supported" | response_schema rejeitado; Pydantic dict usa additionalProperties | f1b5c9c |
| 12 | Gemini: "Duchy tuple validation" | dict[str, tuple] não mapeia bem pra JSON schema | 8c45901 |
| 13 | Ollama inventava keys (regions, historical_names) | Prompt descritivo; modelo pequeno copia exemplos melhor | a4b301a |
| 14 | Credenciais sumiam no restart | In-memory only (D-14) | 8b76e92 |

## Decisões que revogamos

**D-14 "credenciais nunca em disco" → revogada.** Usuário pediu persistência. Justificativa: tool local single-user, DB fica em `~/.medieval-forge/` (user-scoped), mesmo modelo do gh/git. Nova tabela `llm_credentials`.

**`response_schema` no Gemini → removido.** Gemini rejeita qualquer schema com `additionalProperties` (que Pydantic sempre emite pra `dict[str, X]`). Fallback: `response_mime_type=json` + regras no prompt + validação Pydantic nossa.

**Schema `duchies: dict[str, tuple[str, str]]` → trocado pra `dict[str, Duchy]`.** Modelo aninhado com `{kingdom_id, name}`. Tuplas viram arrays em JSON e confundem LLMs. Frontend só usa `Object.keys(duchies).length`, então mudança é transparente pra UI.

## Pendências (confirmadas pelo usuário como não-bloqueantes)

- **429 em Claude/Gemini** — não é bug. Confusão conta Pro (web) vs. API. Usuário precisa criar key API separada em console.anthropic.com / aistudio.google.com com billing.
- **Gemini OAuth** — `GOOGLE_CLIENT_CONFIG` tem placeholders. Config Google Cloud Console é trabalho do usuário, não do código.
- **OpenCode como provider** — usuário disse "vou testar em casa". Pendente investigar se OpenCode expõe API local ou se dá pra piggyback credential file.
- **Testar Ollama com modelo grande** — máquina atual sem RAM suficiente; usuário vai testar em casa.

## Próximos passos sugeridos

- Quando testar Ollama em casa: se `qwen2.5:14b` ou `llama3.1:8b` falhar no formato, capturar as 3 tentativas do bloco vermelho e ajustar prompt/parser.
- Investigar OpenCode: `dir %USERPROFILE%\.opencode` e ver se há arquivo de credencial reutilizável.
- Considerar `/gsd-audit-uat` pra formalizar os HUMAN-UAT items da Fase 3 e avançar pra Fase 4.
