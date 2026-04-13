import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, test, vi } from "vitest";

import { SettingsRoute } from "@/routes/settings";

vi.mock("@/api/endpoints/user", () => ({
  useUserProfile: () => ({
    data: {
      username: "lining",
      is_active: true,
      is_superuser: true,
      nickname: "Lining",
      email: "lining@example.com",
      bio: "bio",
    },
  }),
}));

vi.mock("@/api/endpoints/agent", () => ({
  useBuiltinTools: () => ({
    data: [],
  }),
}));

vi.mock("@/api/endpoints/settings", () => ({
  useMcpServers: () => ({
    data: [
      {
        id: "mcp-1",
        name: "Tavily MCP",
        transport: "streamable_http",
        url: "https://mcp.example.com",
        updated_at: "2026-04-14T00:00:00Z",
        enabled: true,
      },
    ],
  }),
  useChatModels: () => ({
    data: [
      {
        id: "llm-1",
        name: "GPT-4.1",
        provider: "openai_compatible",
        model_name: "gpt-4.1",
        is_default: false,
      },
    ],
  }),
  useEmbeddingModels: () => ({
    data: [],
  }),
  useRerankModels: () => ({
    data: [],
  }),
}));

vi.mock("@/features/settings/forms", () => ({
  ProfileForm: () => <div>profile-form</div>,
  McpServerForm: (props: { mode?: string; server?: { name?: string } | null }) => (
    <div>{`mcp-form:${props.mode}:${props.server?.name ?? ""}`}</div>
  ),
  ChatModelForm: (props: { mode?: string; model?: { name?: string } | null }) => (
    <div>{`chat-form:${props.mode}:${props.model?.name ?? ""}`}</div>
  ),
  EmbeddingModelForm: () => <div>embedding-form</div>,
  RerankModelForm: () => <div>rerank-form</div>,
}));

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/settings/*" element={<SettingsRoute />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SettingsRoute edit dialogs", () => {
  test("opens create dialogs from add buttons", async () => {
    const user = userEvent.setup();

    renderRoute("/settings/mcp-servers");
    await user.click(screen.getByRole("button", { name: "新增 MCP" }));
    expect(screen.getByRole("heading", { name: "新增 MCP Server" })).toBeInTheDocument();
    expect(screen.getByText("mcp-form:create:")).toBeInTheDocument();
  });

  test("opens MCP edit dialog with initial server data", async () => {
    const user = userEvent.setup();

    renderRoute("/settings/mcp-servers");

    await user.click(screen.getByRole("button", { name: "编辑 MCP" }));

    expect(screen.getByText("编辑 MCP Server")).toBeInTheDocument();
    expect(screen.getByText("mcp-form:edit:Tavily MCP")).toBeInTheDocument();
  });

  test("opens Chat Model edit dialog with initial model data", async () => {
    const user = userEvent.setup();

    renderRoute("/settings/models/chat");

    await user.click(screen.getByRole("button", { name: "编辑 Chat Model" }));

    expect(
      screen.getByRole("heading", { name: "编辑 Chat Model" }),
    ).toBeInTheDocument();
    expect(screen.getByText("chat-form:edit:GPT-4.1")).toBeInTheDocument();
  });
});
