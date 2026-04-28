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

// Full 12-category CodexResult fixture used across most tests
const mockCodexResult = {
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
  religion: {
    summary: "Christianity",
    entries: [{ id: "R_CATH", name: "Latin Christianity", description: "The dominant faith." }],
  },
  culture: { summary: "", entries: [] },
  economy: { summary: "", entries: [] },
  military: { summary: "", entries: [] },
  events: { summary: "", entries: [] },
};

// ─── Test Setup ───────────────────────────────────────────────────────────────

beforeEach(() => {
  // Default fetch mock: providers + health return successfully, cached returns 404
  vi.spyOn(globalThis, "fetch").mockImplementation((url: RequestInfo | URL) => {
    const urlStr = String(url);
    if (urlStr.includes("/api/llm/providers")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockProviders),
      } as Response);
    }
    if (urlStr.includes("/api/llm/health")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockHealthAllHealthy),
      } as Response);
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
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockProviders),
        } as Response);
      }
      if (urlStr.includes("/api/llm/health")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthAllHealthy),
        } as Response);
      }
      if (urlStr.includes("/codex/cached")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockCodexResult),
        } as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(
        <Wrapper>
          <CodexViewer projectId="proj-1" />
        </Wrapper>
      );
    });

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
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockProviders),
        } as Response);
      }
      if (urlStr.includes("/api/llm/health")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthAllHealthy),
        } as Response);
      }
      if (urlStr.includes("/codex/cached")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockCodexResult),
        } as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(
        <Wrapper>
          <CodexViewer projectId="proj-2" />
        </Wrapper>
      );
    });

    // Wait for tabs to appear
    await screen.findByTestId("codex-tab-religion");

    // Click the religion tab
    await act(async () => {
      fireEvent.click(screen.getByTestId("codex-tab-religion"));
    });

    // Religion entry should be visible
    await waitFor(() => {
      expect(screen.getByText("Latin Christianity")).toBeInTheDocument();
    });

    // Dynasty entry should NOT be visible (different tab)
    expect(screen.queryByText("House of Aviz")).not.toBeInTheDocument();
  });

  it("renders markdown bold in entry description as a strong tag", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url: RequestInfo | URL) => {
      const urlStr = String(url);
      if (urlStr.includes("/api/llm/providers")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockProviders),
        } as Response);
      }
      if (urlStr.includes("/api/llm/health")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthAllHealthy),
        } as Response);
      }
      if (urlStr.includes("/codex/cached")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockCodexResult),
        } as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    const { container } = render(
      <Wrapper>
        <CodexViewer projectId="proj-3" />
      </Wrapper>
    );

    // Wait for tabs to appear
    await screen.findByTestId("codex-tab-dynasty");

    // Click the dynasty tab (description contains "**Royal** dynasty of Portugal.")
    await act(async () => {
      fireEvent.click(screen.getByTestId("codex-tab-dynasty"));
    });

    // react-markdown should convert **Royal** to <strong>Royal</strong>
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
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockProviders),
        } as Response);
      }
      if (urlStr.includes("/api/llm/health")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthAllHealthy),
        } as Response);
      }
      if (urlStr.includes("/codex/cached")) {
        // events has entries: [] in mockCodexResult
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockCodexResult),
        } as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(
        <Wrapper>
          <CodexViewer projectId="proj-4" />
        </Wrapper>
      );
    });

    // Wait for tabs, then click events tab (which has zero entries)
    await screen.findByTestId("codex-tab-events");

    await act(async () => {
      fireEvent.click(screen.getByTestId("codex-tab-events"));
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
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockProviders),
        } as Response);
      }
      if (urlStr.includes("/api/llm/health")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealthAllHealthy),
        } as Response);
      }
      if (urlStr.includes("/codex/cached")) {
        return Promise.resolve({ status: 404, ok: false } as Response);
      }
      if (urlStr.includes("/codex")) {
        // Return SSE stream with ERROR token
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(encoder.encode("data: ERROR: provider unreachable\n\n"));
            controller.close();
          },
        });
        return Promise.resolve({
          ok: true,
          body: stream,
        } as unknown as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(
        <Wrapper>
          <CodexViewer projectId="proj-5" />
        </Wrapper>
      );
    });

    // Click "Gerar Codex" to trigger the stream
    const gerarButton = await screen.findByText("Gerar Codex");
    await act(async () => {
      fireEvent.click(gerarButton);
    });

    // Error message from SSE ERROR token should appear
    await waitFor(() => {
      expect(screen.getByText("provider unreachable")).toBeInTheDocument();
    });
  });
});
