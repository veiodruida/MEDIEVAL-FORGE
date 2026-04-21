import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Theme } from "@radix-ui/themes";
import { ResearchDialog } from "./ResearchDialog";
import { useResearchStore } from "../../stores/useResearchStore";

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
  {
    provider_id: "openai",
    display_name: "OpenAI",
    auth_methods: [{ type: "api_key", env_var: "OPENAI_API_KEY" }],
    configured: false,
    healthy: true,
    default_model: "gpt-4o-mini",
  },
  {
    provider_id: "gemini",
    display_name: "Google Gemini",
    auth_methods: [{ type: "oauth", authorize_url: null, scopes: [] }],
    configured: false,
    healthy: true,
    default_model: "gemini-pro",
  },
  {
    provider_id: "ollama",
    display_name: "Ollama (local)",
    auth_methods: [{ type: "none" }],
    configured: true,
    healthy: true,
    default_model: "qwen2.5:7b",
  },
];

const mockHealthAllHealthy = {
  claude: { healthy: true, message: "ok" },
  openai: { healthy: true, message: "ok" },
  gemini: { healthy: true, message: "ok" },
  ollama: { healthy: true, message: "ok" },
};

const mockHealthOllamaDown = {
  claude: { healthy: true, message: "ok" },
  openai: { healthy: true, message: "ok" },
  gemini: { healthy: true, message: "ok" },
  ollama: { healthy: false, message: "unreachable" },
};

// ─── Test Setup ───────────────────────────────────────────────────────────────

beforeEach(() => {
  // Reset store to defaults with dialog open
  useResearchStore.setState({
    dialogOpen: true,
    sheetOpenForProvider: null,
    selectedProviderId: "claude",
    country: "Q29",
    periodStart: 868,
    periodEnd: 900,
    manualJson: "",
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("ResearchDialog", () => {
  it("renders provider list from useProvidersQuery", async () => {
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
      if (urlStr.includes("/research/cached")) {
        return Promise.resolve({ status: 404, ok: false } as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(
        <Wrapper>
          <ResearchDialog projectId="proj-1" />
        </Wrapper>
      );
    });

    expect(await screen.findByText("Claude (Anthropic)")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("Google Gemini")).toBeInTheDocument();
    expect(screen.getByText("Ollama (local)")).toBeInTheDocument();
  });

  it("disables Ollama radio when health.ollama.healthy is false", async () => {
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
          json: () => Promise.resolve(mockHealthOllamaDown),
        } as Response);
      }
      if (urlStr.includes("/research/cached")) {
        return Promise.resolve({ status: 404, ok: false } as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(
        <Wrapper>
          <ResearchDialog projectId="proj-2" />
        </Wrapper>
      );
    });

    // Wait for providers to load
    await screen.findByText("Ollama (local)");

    // Find the Ollama radio item — it should be disabled
    const radioItems = screen.getAllByRole("radio");
    // The last radio is for ollama (order from mockProviders array)
    const ollamaRadio = radioItems[radioItems.length - 1];
    expect(ollamaRadio).toBeDisabled();
  });

  it("disables 'Iniciar pesquisa' button while streaming", async () => {
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
      if (urlStr.includes("/research/cached")) {
        return Promise.resolve({ status: 404, ok: false } as Response);
      }
      if (urlStr.includes("/research")) {
        // Return a stream that never resolves to simulate streaming state
        return new Promise<Response>(() => {});
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(
        <Wrapper>
          <ResearchDialog projectId="proj-3" />
        </Wrapper>
      );
    });

    // Wait for initial render
    const startButton = await screen.findByText("Iniciar pesquisa");
    expect(startButton).not.toBeDisabled();

    // Click start — do NOT await to keep the stream pending
    act(() => {
      fireEvent.click(startButton);
    });

    // After clicking, the button should show "Pesquisando…" and be disabled.
    // Note: "Pesquisando…" appears in both the streaming label and the button,
    // so we query specifically for the button role.
    await waitFor(() => {
      const buttons = screen.getAllByText("Pesquisando…");
      // At least one of them should be a disabled button
      const disabledButton = buttons.find(
        (el) => el.tagName === "BUTTON" || el.closest("button[disabled]") !== null
      );
      expect(disabledButton).toBeDefined();
    });
    const buttons = screen.getAllByText("Pesquisando…");
    const disabledButton = buttons.find((el) => el.tagName === "BUTTON");
    expect(disabledButton).toBeDisabled();
  });

  it("shows cached badge when useCachedResultQuery returns a result", async () => {
    const mockCachedResult = {
      kingdoms: { K1: "Reino de Portugal" },
      duchies: { D1: ["K1", "Minho"] },
      condados_assignment: [{ condado_id: "C1", kingdom_id: "K1", duchy_id: "D1" }],
      baronies: { C1: [{ name: "Baronia", lon: -8.0, lat: 41.0 }] },
    };

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
      if (urlStr.includes("/research/cached")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockCachedResult),
        } as Response);
      }
      return Promise.resolve({ ok: false, status: 404 } as Response);
    });

    const { Wrapper } = makeWrapper();

    await act(async () => {
      render(
        <Wrapper>
          <ResearchDialog projectId="proj-4" />
        </Wrapper>
      );
    });

    // Wait for the cached result badge to appear
    expect(await screen.findByText("Resultado em cache")).toBeInTheDocument();
    expect(screen.getByText("Forçar nova pesquisa")).toBeInTheDocument();
  });

  it("shows manual JSON editor after 3 retry notices + error", async () => {
    const encoder = new TextEncoder();
    const sseChunks = [
      "data: Tentativa 1/3: ValidationError\n\n",
      "data: Tentativa 2/3: ValidationError\n\n",
      "data: Tentativa 3/3: ValidationError\n\n",
      "data: ERROR: max retries exceeded\n\n",
    ];
    let chunkIndex = 0;

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
      if (urlStr.includes("/research/cached")) {
        return Promise.resolve({ status: 404, ok: false } as Response);
      }
      if (urlStr.includes("/research")) {
        chunkIndex = 0;
        const stream = new ReadableStream<Uint8Array>({
          pull(controller) {
            if (chunkIndex < sseChunks.length) {
              controller.enqueue(encoder.encode(sseChunks[chunkIndex++]));
            } else {
              controller.close();
            }
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
          <ResearchDialog projectId="proj-5" />
        </Wrapper>
      );
    });

    // Click start to trigger the stream
    const startButton = await screen.findByText("Iniciar pesquisa");
    await act(async () => {
      fireEvent.click(startButton);
    });

    // After max retries + error, the manual editor should appear
    expect(await screen.findByText("Falha após 3 tentativas")).toBeInTheDocument();
    expect(screen.getByText("Revalidar JSON")).toBeInTheDocument();
    // TextArea should be present
    expect(screen.getByPlaceholderText("Cola ou edita o JSON aqui…")).toBeInTheDocument();
  });
});
