import { useState } from "react";
import { Badge, Button, Callout, Flex, Heading, Separator, Text, TextArea } from "@radix-ui/themes";
import { fetchResearchPrompt, submitManualResearch, type ResearchResult } from "../../api/research";

interface ManualResearchPanelProps {
  projectId: string;
  onResult: (result: ResearchResult) => void;
}

export function ManualResearchPanel({ projectId, onResult }: ManualResearchPanelProps) {
  const [prompt, setPrompt] = useState<string>("");
  const [promptLoading, setPromptLoading] = useState(false);
  const [promptError, setPromptError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [response, setResponse] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const handleGeneratePrompt = async () => {
    setPromptLoading(true);
    setPromptError(null);
    setCopied(false);
    try {
      const p = await fetchResearchPrompt(projectId);
      setPrompt(p);
    } catch (e) {
      setPromptError(e instanceof Error ? e.message : String(e));
    } finally {
      setPromptLoading(false);
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setPromptError("Não foi possível copiar. Selecione o texto manualmente.");
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(false);
    try {
      const result = await submitManualResearch(projectId, response);
      onResult(result);
      setSubmitSuccess(true);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Flex direction="column" gap="4">
      {/* Step 1 — Generate + copy prompt */}
      <Flex direction="column" gap="2">
        <Heading size="3">1. Gerar e copiar o prompt</Heading>
        <Text size="2" color="gray">
          Gera o prompt, cola em qualquer chat (ChatGPT, Claude.ai, Gemini, etc.) e pede o JSON.
        </Text>
        <Flex gap="2">
          <Button onClick={handleGeneratePrompt} disabled={promptLoading}>
            {promptLoading ? "Gerando…" : prompt ? "Regerar prompt" : "Gerar prompt"}
          </Button>
          {prompt && (
            <Button variant="soft" onClick={handleCopy}>
              {copied ? "Copiado" : "Copiar"}
            </Button>
          )}
        </Flex>
        {promptError && (
          <Callout.Root color="red" size="1">
            <Callout.Text>{promptError}</Callout.Text>
          </Callout.Root>
        )}
        {prompt && (
          <TextArea
            value={prompt}
            readOnly
            style={{ minHeight: 160, fontFamily: "monospace", fontSize: 11 }}
          />
        )}
      </Flex>

      <Separator size="4" />

      {/* Step 2 — Paste + submit response */}
      <Flex direction="column" gap="2">
        <Heading size="3">2. Cole a resposta do chat externo abaixo</Heading>
        <Text size="2" color="gray">
          Cole aqui o JSON retornado pelo chat. Aceitamos o JSON puro ou dentro de um bloco ```json … ```.
        </Text>
        <TextArea
          value={response}
          onChange={(e) => setResponse(e.target.value)}
          placeholder='{"kingdoms": {...}, "duchies": {...}, "condados_assignment": [...], "baronies": {...}}'
          style={{ minHeight: 180, fontFamily: "monospace", fontSize: 11 }}
          disabled={submitting}
        />
        {submitError && (
          <Callout.Root color="red" size="1">
            <Callout.Text style={{ whiteSpace: "pre-wrap" }}>{submitError}</Callout.Text>
          </Callout.Root>
        )}
        {submitSuccess && (
          <Badge color="green" size="2">
            Resposta aceita — territórios populados.
          </Badge>
        )}
        <Flex>
          <Button
            color="blue"
            onClick={handleSubmit}
            disabled={submitting || response.trim().length === 0}
          >
            {submitting ? "Enviando…" : "Enviar resposta"}
          </Button>
        </Flex>
      </Flex>
    </Flex>
  );
}
