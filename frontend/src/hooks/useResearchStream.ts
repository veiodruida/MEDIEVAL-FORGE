import { useCallback, useRef, useState } from "react";
import type { ResearchResult } from "../api/research";

type Status = "idle" | "streaming" | "cached" | "success" | "error";

export function useResearchStream(projectId: string) {
  const [messages, setMessages] = useState<string[]>([]);
  const [retryNotices, setRetryNotices] = useState<string[]>([]);
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const start = useCallback(
    async (provider: string, forceRefresh = false) => {
      cancel();
      setMessages([]);
      setRetryNotices([]);
      setResult(null);
      setError(null);
      setStatus("streaming");
      const ac = new AbortController();
      abortRef.current = ac;
      try {
        const r = await fetch(
          `/api/projects/${projectId}/research?provider=${provider}&force_refresh=${forceRefresh}`,
          { method: "POST", signal: ac.signal }
        );
        if (!r.ok || !r.body) {
          setStatus("error");
          setError(`HTTP ${r.status}`);
          return;
        }
        const reader = r.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let idx;
          while ((idx = buffer.indexOf("\n\n")) >= 0) {
            const chunk = buffer.slice(0, idx).trim();
            buffer = buffer.slice(idx + 2);
            if (!chunk.startsWith("data:")) continue;
            const payload = chunk.slice(5).trim();
            if (payload === "DONE") {
              setStatus((s) => (s === "cached" ? "cached" : "success"));
              continue;
            }
            if (payload === "cached") {
              setStatus("cached");
              continue;
            }
            if (payload.startsWith("ERROR:")) {
              setStatus("error");
              setError(payload.slice(6).trim());
              continue;
            }
            if (payload.startsWith("RESULT:")) {
              try {
                setResult(JSON.parse(payload.slice(7).trim()));
              } catch (e) {
                setError(`Bad RESULT JSON: ${e}`);
                setStatus("error");
              }
              continue;
            }
            if (payload.startsWith("Tentativa")) {
              setRetryNotices((prev) => [...prev, payload]);
              continue;
            }
            setMessages((prev) => [...prev, payload]);
          }
        }
      } catch (e: unknown) {
        if (e instanceof Error && e.name !== "AbortError") {
          setStatus("error");
          setError(String(e));
        }
      }
    },
    [projectId, cancel]
  );

  return { start, cancel, messages, retryNotices, result, status, error };
}
