import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Theme } from "@radix-ui/themes";
import { AssignmentEditor } from "./AssignmentEditor";
import { useResearchStore } from "../../stores/useResearchStore";
import type { MapResearchResult } from "../../api/edit";

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

// ─── Fixture (explicit numeric/symbolic IDs per project memory) ───────────────

const FIXTURE: MapResearchResult = {
  kingdoms: { K_LEON: "Reino de León" },
  duchies: {
    D_LEON: { kingdom_id: "K_LEON", name: "Ducado de León" },
    D_BURGOS: { kingdom_id: "K_LEON", name: "Ducado de Burgos" },
  },
  condados: [
    { id: "C_LEON", name: "Condado de León", kingdom_id: "K_LEON", duchy_id: "D_LEON" },
    { id: "C_BURGOS", name: "Condado de Burgos", kingdom_id: "K_LEON", duchy_id: "D_BURGOS" },
  ],
  barony_assignments: { B_1: "C_LEON", B_2: "C_LEON", B_3: "C_BURGOS" },
};

// ─── Test Setup ───────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("AssignmentEditor", () => {
  it("renders all barony rows with correct current condado in Select and Salvar disabled initially", async () => {
    const { Wrapper } = makeWrapper();
    render(
      <Wrapper>
        <AssignmentEditor
          open={true}
          onOpenChange={vi.fn()}
          projectId="p1"
          researchResult={FIXTURE}
        />
      </Wrapper>,
    );

    // Each barony row must be visible by testid
    expect(screen.getByTestId("barony-row-B_1")).toBeInTheDocument();
    expect(screen.getByTestId("barony-row-B_2")).toBeInTheDocument();
    expect(screen.getByTestId("barony-row-B_3")).toBeInTheDocument();

    // Each Select trigger shows the current condado label
    // B_1 → C_LEON → "Condado de León"
    expect(screen.getByTestId("barony-row-B_1")).toHaveTextContent("Condado de León");
    // B_2 → C_LEON → "Condado de León"
    expect(screen.getByTestId("barony-row-B_2")).toHaveTextContent("Condado de León");
    // B_3 → C_BURGOS → "Condado de Burgos"
    expect(screen.getByTestId("barony-row-B_3")).toHaveTextContent("Condado de Burgos");

    // Salvar must be disabled initially (no changes)
    const saveButton = screen.getByTestId("save-button");
    expect(saveButton).toBeDisabled();
  });

  it("changing a barony's condado then Salvar calls PATCH with only the changed barony delta", async () => {
    const updatedResult: MapResearchResult = {
      ...FIXTURE,
      barony_assignments: { B_1: "C_LEON", B_2: "C_BURGOS", B_3: "C_BURGOS" },
    };
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ result: updatedResult }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchSpy);

    const { Wrapper } = makeWrapper();
    render(
      <Wrapper>
        <AssignmentEditor
          open={true}
          onOpenChange={vi.fn()}
          projectId="p1"
          researchResult={FIXTURE}
        />
      </Wrapper>,
    );

    // Click the B_2 Select trigger to open the dropdown.
    // scrollIntoView is stubbed in test-setup.ts to avoid jsdom "not a function" error.
    const b2Trigger = screen.getByTestId("barony-row-B_2");
    fireEvent.click(b2Trigger);

    // Radix Select renders items with role="option" in the viewport after trigger click.
    // Use findByRole to get the C_BURGOS option unambiguously.
    const burgosOption = await screen.findByRole("option", {
      name: /Condado de Burgos \(C_BURGOS\)/,
    });
    fireEvent.click(burgosOption);

    const saveButton = screen.getByTestId("save-button");

    await waitFor(() => {
      expect(saveButton).not.toBeDisabled();
    });

    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/projects/p1/research/assignments",
        expect.objectContaining({
          method: "PATCH",
          headers: expect.objectContaining({ "Content-Type": "application/json" }),
          body: JSON.stringify({ barony_assignments: { B_2: "C_BURGOS" } }),
        }),
      );
    });
  });

  it("renaming a condado then Salvar sends only that condado rename without duchy_id", async () => {
    const updatedResult: MapResearchResult = {
      ...FIXTURE,
      condados: [
        { id: "C_LEON", name: "Reino Antigo de León", kingdom_id: "K_LEON", duchy_id: "D_LEON" },
        { id: "C_BURGOS", name: "Condado de Burgos", kingdom_id: "K_LEON", duchy_id: "D_BURGOS" },
      ],
    };
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ result: updatedResult }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchSpy);

    const { Wrapper } = makeWrapper();
    render(
      <Wrapper>
        <AssignmentEditor
          open={true}
          onOpenChange={vi.fn()}
          projectId="p1"
          researchResult={FIXTURE}
        />
      </Wrapper>,
    );

    // Edit C_LEON name TextField
    const nameField = screen.getByTestId("condado-name-C_LEON");
    fireEvent.change(nameField, { target: { value: "Reino Antigo de León" } });

    // Salvar should be enabled
    const saveButton = screen.getByTestId("save-button");
    await waitFor(() => {
      expect(saveButton).not.toBeDisabled();
    });

    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/projects/p1/research/assignments",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({
            condado_renames: { C_LEON: { name: "Reino Antigo de León" } },
          }),
        }),
      );
    });
  });

  it("backend 400 error displays Callout with error text and dialog stays open; 1000-char error truncated to ≤600 chars", async () => {
    const longError = "x".repeat(1000);
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: () => Promise.resolve(longError),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchSpy);

    const { Wrapper } = makeWrapper();
    const onOpenChange = vi.fn();
    render(
      <Wrapper>
        <AssignmentEditor
          open={true}
          onOpenChange={onOpenChange}
          projectId="p1"
          researchResult={FIXTURE}
        />
      </Wrapper>,
    );

    // Make a change (rename C_LEON) to enable Salvar
    const nameField = screen.getByTestId("condado-name-C_LEON");
    fireEvent.change(nameField, { target: { value: "Novo Nome" } });

    const saveButton = screen.getByTestId("save-button");
    await waitFor(() => expect(saveButton).not.toBeDisabled());
    fireEvent.click(saveButton);

    // Error callout must appear
    const callout = await screen.findByTestId("error-callout");
    expect(callout).toBeInTheDocument();

    // Text must be truncated to ≤600 chars
    const renderedText = callout.textContent ?? "";
    expect(renderedText.length).toBeLessThanOrEqual(600);

    // Dialog stays open (onOpenChange(false) must NOT be called)
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("success calls setManualResult with returned result and onOpenChange(false)", async () => {
    const updatedResult: MapResearchResult = {
      ...FIXTURE,
      barony_assignments: { B_1: "C_LEON", B_2: "C_BURGOS", B_3: "C_BURGOS" },
    };
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ result: updatedResult }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchSpy);

    // Spy on setManualResult via store injection
    const setManualResultSpy = vi.fn();
    useResearchStore.setState({ setManualResult: setManualResultSpy });

    const onOpenChange = vi.fn();
    const { Wrapper } = makeWrapper();
    render(
      <Wrapper>
        <AssignmentEditor
          open={true}
          onOpenChange={onOpenChange}
          projectId="p1"
          researchResult={FIXTURE}
        />
      </Wrapper>,
    );

    // Make a change to enable Salvar
    const nameField = screen.getByTestId("condado-name-C_LEON");
    fireEvent.change(nameField, { target: { value: "Reino Atualizado" } });

    const saveButton = screen.getByTestId("save-button");
    await waitFor(() => expect(saveButton).not.toBeDisabled());
    fireEvent.click(saveButton);

    // After success: setManualResult called with the returned result, dialog closed
    await waitFor(() => {
      expect(setManualResultSpy).toHaveBeenCalledTimes(1);
      expect(setManualResultSpy).toHaveBeenCalledWith(updatedResult);
    });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
