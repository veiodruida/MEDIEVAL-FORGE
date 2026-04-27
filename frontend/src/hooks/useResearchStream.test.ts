import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useResearchStream } from "./useResearchStream";

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

describe("useResearchStream", () => {
  it("parses SSE messages and classifies tokens, cached, RESULT, DONE, ERROR", async () => {
    const mockResult = {
      kingdoms: { K1: "Kingdom 1" },
      duchies: { D1: ["K1", "Duchy 1"] as [string, string] },
      condados_assignment: [{ condado_id: "C1", kingdom_id: "K1", duchy_id: "D1" }],
      baronies: { C1: [{ name: "Barony 1", lon: -8.0, lat: 41.0 }] },
    };

    const sseChunks = [
      "data: starting claude (claude-sonnet)\n\n",
      "data: Some streamed token\n\n",
      `data: RESULT: ${JSON.stringify(mockResult)}\n\n`,
      "data: DONE\n\n",
    ];

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      body: makeStream(sseChunks),
    } as unknown as Response);

    const { result } = renderHook(() => useResearchStream("project-1"));

    await act(async () => {
      await result.current.start("claude", false);
    });

    expect(result.current.status).toBe("success");
    expect(result.current.result).toEqual(mockResult);
    // messages is StreamMessage[] (each has text + ts) — extract the text values
    expect(result.current.messages.map((m) => m.text)).toContain("Some streamed token");
    expect(result.current.error).toBeNull();
  });

  it("handles cached marker → status='cached'", async () => {
    const mockResult = {
      kingdoms: { K1: "Test Kingdom" },
      duchies: {},
      condados_assignment: [],
      baronies: {},
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

    const { result } = renderHook(() => useResearchStream("project-2"));

    await act(async () => {
      await result.current.start("claude", false);
    });

    expect(result.current.status).toBe("cached");
    expect(result.current.result).toEqual(mockResult);
  });

  it("captures retry notices into retryNotices array", async () => {
    const sseChunks = [
      "data: Tentativa 1/3: ValidationError: missing field 'kingdoms'\n\n",
      "data: ERROR: max retries exceeded\n\n",
    ];

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      body: makeStream(sseChunks),
    } as unknown as Response);

    const { result } = renderHook(() => useResearchStream("project-3"));

    await act(async () => {
      await result.current.start("claude", false);
    });

    expect(result.current.retryNotices).toHaveLength(1);
    expect(result.current.retryNotices[0]).toContain("Tentativa 1/3");
  });

  it("captures ERROR messages and sets status='error'", async () => {
    const sseChunks = ["data: ERROR: foo\n\n"];

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      body: makeStream(sseChunks),
    } as unknown as Response);

    const { result } = renderHook(() => useResearchStream("project-4"));

    await act(async () => {
      await result.current.start("claude", false);
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toBe("foo");
  });
});
