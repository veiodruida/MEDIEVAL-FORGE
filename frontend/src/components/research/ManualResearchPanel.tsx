import { useState, type ChangeEvent } from "react";
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

  const handleDownload = () => {
    const blob = new Blob([prompt], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "prompt.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleFileUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      setResponse(text);
    };
    reader.onerror = () => {
      setSubmitError("Não foi possível ler o arquivo.");
    };
    reader.readAsText(file, "utf-8");
    // Reset input so the same file can be reselected
    e.target.value = "";
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
            <>
              <Button variant="soft" onClick={handleCopy}>
                {copied ? "Copiado" : "Copiar"}
              </Button>
              <Button variant="soft" onClick={handleDownload}>
                Baixar prompt
              </Button>
            </>
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
        <Flex gap="2" align="center">
          <Button variant="soft" asChild>
            <label style={{ cursor: "pointer" }}>
              Carregar arquivo
              <input
                type="file"
                accept=".txt,.json,application/json,text/plain"
                style={{ display: "none" }}
                onChange={handleFileUpload}
              />
            </label>
          </Button>
          <Text size="1" color="gray">ou cole manualmente abaixo</Text>
        </Flex>
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
