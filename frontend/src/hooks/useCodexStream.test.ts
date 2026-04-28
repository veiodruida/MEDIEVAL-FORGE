import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCodexStream } from "./useCodexStream";

/**
 * Build a mock ReadableStream from a sequence of SSE chunks.
 * Each element in `chunks` is a string that will be encoded and streamed.
 */
function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index++]));
      } else {
        controller.close();
      }
    },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useCodexStream", () => {
  it("parses SSE messages and classifies tokens, cached, RESULT, DONE, ERROR", async () => {
    const mockResult = {
      currency: { summary: "", entries: [] },
      attributes: { summary: "", entries: [] },
      health: { summary: "", entries: [] },
      traits: { summary: "", entries: [] },
      feudal: { summary: "", entries: [] },
      politics: { summary: "", entries: [] },
      dynasty: {
        summary: "House of Aviz",
        entries: [
          { id: "D_AVIZ", name: "House of Aviz", description: "**Royal** dynasty of Portugal." },
        ],
      },
      religion: { summary: "", entries: [] },
      culture: { summary: "", entries: [] },
      economy: { summary: "", entries: [] },
      military: { summary: "", entries: [] },
      events: { summary: "", entries: [] },
    };

    const sseChunks = [
      "data: starting codex run\n\n",
      "data: Some streamed token\n\n",
      `data: RESULT: ${JSON.stringify(mockResult)}\n\n`,
      "data: DONE\n\n",
    ];

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      body: makeStream(sseChunks),
    } as unknown as Response);

    const { result } = renderHook(() => useCodexStream("project-1"));

    await act(async () => {
      await result.current.start("claude", false);
    });

    expect(result.current.status).toBe("success");
    expect(result.current.result).toEqual(mockResult);
    expect(result.current.messages.map((m) => m.text)).toContain("Some streamed token");
    expect(result.current.error).toBeNull();
  });

  it("handles cached marker and sets status to cached", async () => {
    const mockResult = {
      currency: { summary: "", entries: [] },
      attributes: { summary: "", entries: [] },
      health: { summary: "", entries: [] },
      traits: { summary: "", entries: [] },
      feudal: { summary: "", entries: [] },
      politics: { summary: "", entries: [] },
      dynasty: {
        summary: "House of Aviz",
        entries: [
          { id: "D_AVIZ", name: "House of Aviz", description: "**Royal** dynasty of Portugal." },
        ],
      },
      religion: { summary: "", entries: [] },
      culture: { summary: "", entries: [] },
      economy: { summary: "", entries: [] },
      military: { summary: "", entries: [] },
      events: { summary: "", entries: [] },
    };

    const sseChunks = [
      "data: cached\n\n",
      `data: RESULT: ${JSON.stringify(mockResult)}\n\n`,
      "data: DONE\n\n",
    ];

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      body: makeStream(sseChunks),
    } as unknown as Response);

    const { result } = renderHook(() => useCodexStream("project-2"));

    await act(async () => {
      await result.current.start("claude", false);
    });

    expect(result.current.status).toBe("cached");
    expect(result.current.result).toEqual(mockResult);
  });

  it("captures retry notices into retryNotices array", async () => {
    const sseChunks = [
      "data: Tentativa 1/3: ValidationError: missing field 'dynasty'\n\n",
      "data: ERROR: max retries exceeded\n\n",
    ];

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      body: makeStream(sseChunks),
    } as unknown as Response);

    const { result } = renderHook(() => useCodexStream("project-3"));

    await act(async () => {
      await result.current.start("claude", false);
    });

    expect(result.current.retryNotices).toHaveLength(1);
    expect(result.current.retryNotices[0]).toContain("Tentativa 1/3");
    expect(result.current.retryNotices[0]).toContain("missing field 'dynasty'");
  });

  it("captures ERROR messages and sets status to error", async () => {
    const sseChunks = ["data: ERROR: provider unreachable\n\n"];

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      body: makeStream(sseChunks),
    } as unknown as Response);

    const { result } = renderHook(() => useCodexStream("project-4"));

    await act(async () => {
      await result.current.start("claude", false);
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toBe("provider unreachable");
  });
});
