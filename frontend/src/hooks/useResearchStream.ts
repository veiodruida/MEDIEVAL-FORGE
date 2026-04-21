import { useCallback, useEffect, useRef, useState } from "react";
import type { ResearchResult } from "../api/research";

type Status = "idle" | "streaming" | "cached" | "success" | "error" | "cancelled";

export type StreamMessage = { text: string; ts: number };

export function useResearchStream(projectId: string) {
  const [messages, setMessages] = useState<StreamMessage[]>([]);
  const [retryNotices, setRetryNotices] = useState<string[]>([]);
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());
  const abortRef = useRef<AbortController | null>(null);

  // Tick "now" every 500ms while streaming so the elapsed counter updates.
  useEffect(() => {
    if (status !== "streaming") return;
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, [status]);

  const elapsedMs = startedAt !== null ? now - startedAt : 0;

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("cancelled");
  }, []);

  const start = useCallback(
    async (provider: string, forceRefresh = false) => {
      abortRef.current?.abort();
      abortRef.current = null;
      setMessages([]);
      setRetryNotices([]);
      setResult(null);
      setError(null);
      setStatus("streaming");
      const t0 = Date.now();
      setStartedAt(t0);
      setNow(t0);
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
            setMessages((prev) => [...prev, { text: payload, ts: Date.now() }]);
          }
        }
      } catch (e: unknown) {
        if (e instanceof Error && e.name !== "AbortError") {
          setStatus("error");
          setError(String(e));
        }
      }
    },
    [projectId]
  );

  return { start, cancel, messages, retryNotices, result, status, error, elapsedMs };
}
