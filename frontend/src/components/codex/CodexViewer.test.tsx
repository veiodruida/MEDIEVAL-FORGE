import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Theme } from "@radix-ui/themes";
import { CodexViewer } from "./CodexViewer";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <Theme>{children}</Theme>
    </QueryClientProvider>
  );
  return { Wrapper, qc };
}

/**
 * Click a Radix Tabs.Trigger properly in jsdom.
 *
 * Radix UI tab triggers use pointerdown internally to switch tabs. A plain
 * fireEvent.click does not fire pointerdown, so the tab state never changes.
 * This helper dispatches the full pointer + mouse + click sequence that Radix
 * listens to, matching how a real browser user interaction works.
 */
function clickRadixTab(element: HTMLElement) {
  fireEvent.pointerDown(element);
  fireEvent.mouseDown(element);
  fireEvent.pointerUp(element);
  fireEvent.mouseUp(element);
  fireEvent.click(element);
}

const mockProviders = [
  {
    provider_id: "claude",
    display_name: "Claude (Anthropic)",
    auth_methods: [{ type: "cli", cli_command: "claude", auth_file_path: "~/.claude" }],
    configured: true,
    healthy: true,
    default_model: "claude-sonnet-4-6",
  },
];

const mockHealthAllHealthy = {
  claude: { healthy: true, message: "ok" },
};

// Full 12-category CodexResult fixture used across most tests.
// dynasty has one entry (id D_AVIZ, bold description).
// religion has one entry (id R_CATH).
// events has zero entries — used for empty-state test.
const mockCodexResult = {
  currency:   { summary: "", entries: [] },
  attributes: { summary: "", entries: [] },
  health:     { summary: "", entries: [] },
  traits:     { summary: "", entries: [] },
  feudal:     { summary: "", entries: [] },
  politics:   { summary: "", entries: [] },
  dynasty: {
    summary: "House of Aviz",
    entries: [
      { id: "D_AVIZ", name: "House of Aviz", description: "**Royal** dynasty of Portugal." },
    ],
  },
  religion: {
    summary: "Christianity",
    entries: [{ id: "R_CATH", name: "Latin Christianity", description: "The dominant faith." }],
  },
  culture:  { summary: "", entries: [] },
  economy:  { summary: "", entries: [] },
  military: { summary: "", entries: [] },
  events:   { summary: "", entries: [] },
};

// ─── Test Setup ───────────────────────────────────────────────────────────────

beforeEach(() => {
  // Default fetch mock: providers + health succeed; cached returns 404.
  // Individual tests override this with vi.spyOn for per-test needs.
  vi.spyOn(globalThis, "fetch").mockImplementation((url: RequestInfo | URL) => {
    const urlStr = String(url);
    if (urlStr.includes("/api/llm/providers")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(mockProviders) } as Response);
    }
    if (urlStr.includes("/api/llm/health")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthAllHealthy) } as Response);
    }
    if (urlStr.includes("/codex/cached")) {
      return Promise.resolve({ status: 404, ok: false } as Response);
    }
    return Promise.resolve({ ok: false, status: 404 } as Response);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("CodexViewer", () => {
  it("renders one tab for each of the 12 codex category keys", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url: RequestInfo | URL) => {
      const urlStr = String(url);
      if (urlStr.includes("/api/llm/providers")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockProviders) } as Response);
      }
      if (urlStr.includes("/api/llm/health")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthAllHealthy) } as Response);
      }
      if (urlStr.includes("/codex/cached")) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(mockCodexResult) } as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(<Wrapper><CodexViewer projectId="proj-1" /></Wrapper>);
    });

    // Wait for the cached query to resolve and tabs to appear
    await screen.findByTestId("codex-tab-currency");

    const categoryKeys = [
      "currency", "attributes", "health", "traits",
      "feudal", "politics", "dynasty", "religion",
      "culture", "economy", "military", "events",
    ];

    for (const key of categoryKeys) {
      expect(screen.getByTestId(`codex-tab-${key}`)).toBeInTheDocument();
    }
  });

  it("clicking a tab shows that category's entries and hides others", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url: RequestInfo | URL) => {
      const urlStr = String(url);
      if (urlStr.includes("/api/llm/providers")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockProviders) } as Response);
      }
      if (urlStr.includes("/api/llm/health")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthAllHealthy) } as Response);
      }
      if (urlStr.includes("/codex/cached")) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(mockCodexResult) } as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(<Wrapper><CodexViewer projectId="proj-2" /></Wrapper>);
    });

    // Wait for tabs to appear (cached query must resolve)
    await screen.findByTestId("codex-tab-religion");

    // Click the religion tab — use full pointer event sequence required by Radix Tabs in jsdom
    await act(async () => {
      clickRadixTab(screen.getByTestId("codex-tab-religion"));
    });

    // Religion entry R_CATH (name "Latin Christianity") should now be in the active panel
    await waitFor(() => {
      expect(screen.getByText("Latin Christianity")).toBeInTheDocument();
    });

    // Dynasty entry D_AVIZ (name "House of Aviz") should NOT be visible
    // (its panel has the hidden attribute so Testing Library ignores it)
    expect(screen.queryByText("House of Aviz")).not.toBeInTheDocument();
  });

  it("renders markdown bold in entry description as a strong tag", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url: RequestInfo | URL) => {
      const urlStr = String(url);
      if (urlStr.includes("/api/llm/providers")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockProviders) } as Response);
      }
      if (urlStr.includes("/api/llm/health")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthAllHealthy) } as Response);
      }
      if (urlStr.includes("/codex/cached")) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(mockCodexResult) } as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    const { container } = render(<Wrapper><CodexViewer projectId="proj-3" /></Wrapper>);

    // Wait for tabs to appear (cached query must resolve)
    await screen.findByTestId("codex-tab-dynasty");

    // Click the dynasty tab — description is "**Royal** dynasty of Portugal."
    // Use full pointer event sequence required by Radix Tabs in jsdom
    await act(async () => {
      clickRadixTab(screen.getByTestId("codex-tab-dynasty"));
    });

    // react-markdown must render **Royal** as <strong>Royal</strong>, not as raw text
    await waitFor(() => {
      const strong = container.querySelector("strong");
      expect(strong).not.toBeNull();
      expect(strong!.textContent).toBe("Royal");
    });
  });

  it("shows empty-state message when the active category has zero entries", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url: RequestInfo | URL) => {
      const urlStr = String(url);
      if (urlStr.includes("/api/llm/providers")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockProviders) } as Response);
      }
      if (urlStr.includes("/api/llm/health")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthAllHealthy) } as Response);
      }
      if (urlStr.includes("/codex/cached")) {
        // events category has entries: [] in mockCodexResult
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(mockCodexResult) } as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(<Wrapper><CodexViewer projectId="proj-4" /></Wrapper>);
    });

    // Wait for tabs to appear, then click events tab (entries: [])
    await screen.findByTestId("codex-tab-events");

    await act(async () => {
      clickRadixTab(screen.getByTestId("codex-tab-events"));
    });

    await waitFor(() => {
      expect(screen.getByText("Nenhuma entrada nesta categoria")).toBeInTheDocument();
    });
  });

  it("renders error UI when SSE stream emits ERROR token", async () => {
    const encoder = new TextEncoder();

    vi.spyOn(globalThis, "fetch").mockImplementation((url: RequestInfo | URL) => {
      const urlStr = String(url);
      if (urlStr.includes("/api/llm/providers")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockProviders) } as Response);
      }
      if (urlStr.includes("/api/llm/health")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockHealthAllHealthy) } as Response);
      }
      if (urlStr.includes("/codex/cached")) {
        return Promise.resolve({ status: 404, ok: false } as Response);
      }
      if (urlStr.includes("/codex")) {
        // POST /codex SSE stream that immediately emits an ERROR token
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(encoder.encode("data: ERROR: provider unreachable\n\n"));
            controller.close();
          },
        });
        return Promise.resolve({ ok: true, body: stream } as unknown as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(<Wrapper><CodexViewer projectId="proj-5" /></Wrapper>);
    });

    // Click "Gerar Codex" to trigger the SSE stream
    const gerarButton = await screen.findByText("Gerar Codex");
    await act(async () => {
      fireEvent.click(gerarButton);
    });

    // Error message "provider unreachable" (from ERROR: token) must appear in the DOM
    await waitFor(() => {
      expect(screen.getByText("provider unreachable")).toBeInTheDocument();
    });
  });
});
