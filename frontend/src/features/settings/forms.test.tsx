import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import {
  ChatModelForm,
  EmbeddingModelForm,
  McpServerForm,
  RerankModelForm,
} from "@/features/settings/forms";

const {
  mockCreateMcpServer,
  mockUpdateMcpServer,
  mockCreateChatModel,
  mockUpdateChatModel,
  mockCreateEmbeddingModel,
  mockUpdateEmbeddingModel,
  mockCreateRerankModel,
  mockUpdateRerankModel,
} = vi.hoisted(() => ({
  mockCreateMcpServer: { mutateAsync: vi.fn(), isPending: false, error: null },
  mockUpdateMcpServer: { mutateAsync: vi.fn(), isPending: false, error: null },
  mockCreateChatModel: { mutateAsync: vi.fn(), isPending: false, error: null },
  mockUpdateChatModel: { mutateAsync: vi.fn(), isPending: false, error: null },
  mockCreateEmbeddingModel: { mutateAsync: vi.fn(), isPending: false, error: null },
  mockUpdateEmbeddingModel: { mutateAsync: vi.fn(), isPending: false, error: null },
  mockCreateRerankModel: { mutateAsync: vi.fn(), isPending: false, error: null },
  mockUpdateRerankModel: { mutateAsync: vi.fn(), isPending: false, error: null },
}));

vi.mock("@/api/endpoints/settings", () => ({
  useCreateMcpServer: () => mockCreateMcpServer,
  useUpdateMcpServer: () => mockUpdateMcpServer,
  useCreateChatModel: () => mockCreateChatModel,
  useUpdateChatModel: () => mockUpdateChatModel,
  useCreateEmbeddingModel: () => mockCreateEmbeddingModel,
  useUpdateEmbeddingModel: () => mockUpdateEmbeddingModel,
  useCreateRerankModel: () => mockCreateRerankModel,
  useUpdateRerankModel: () => mockUpdateRerankModel,
}));

describe("settings edit forms", () => {
  beforeEach(() => {
    mockCreateMcpServer.mutateAsync.mockReset();
    mockUpdateMcpServer.mutateAsync.mockReset();
    mockCreateChatModel.mutateAsync.mockReset();
    mockUpdateChatModel.mutateAsync.mockReset();
    mockCreateEmbeddingModel.mutateAsync.mockReset();
    mockUpdateEmbeddingModel.mutateAsync.mockReset();
    mockCreateRerankModel.mutateAsync.mockReset();
    mockUpdateRerankModel.mutateAsync.mockReset();
  });

  test("McpServerForm fills initial values and submits update payload", async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    mockUpdateMcpServer.mutateAsync.mockResolvedValue({ id: "mcp-1" });

    render(
      <McpServerForm
        mode="edit"
        server={{
          id: "mcp-1",
          name: "Tavily MCP",
          transport: "streamable_http",
          url: "https://mcp.example.com",
          command: null,
          args: null,
          headers: { Authorization: "Bearer token" },
          env: null,
          cwd: null,
          enabled: true,
        }}
        onSuccess={onSuccess}
      />,
    );

    expect(screen.getByLabelText("名称")).toHaveValue("Tavily MCP");
    expect(screen.getByLabelText("URL")).toHaveValue("https://mcp.example.com");

    await user.clear(screen.getByLabelText("名称"));
    await user.type(screen.getByLabelText("名称"), "Tavily MCP Edited");
    await user.click(screen.getByRole("button", { name: "保存 MCP Server" }));

    await waitFor(() =>
      expect(mockUpdateMcpServer.mutateAsync).toHaveBeenCalledWith({
        name: "Tavily MCP Edited",
        transport: "streamable_http",
        url: "https://mcp.example.com",
        command: undefined,
        args: undefined,
        headers: { Authorization: "Bearer token" },
        env: undefined,
        cwd: undefined,
        enabled: true,
      }),
    );
    expect(onSuccess).toHaveBeenCalled();
  });

  test("McpServerForm toggles visible fields by transport without clearing values", async () => {
    const user = userEvent.setup();

    render(<McpServerForm />);

    expect(screen.getByLabelText("URL")).toBeInTheDocument();
    expect(
      screen.queryByLabelText("Command"),
    ).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("URL"), "https://mcp.example.com");
    await user.selectOptions(screen.getByLabelText("Transport"), "stdio");

    expect(screen.getByLabelText("Command")).toBeInTheDocument();
    expect(screen.getByLabelText("CWD")).toBeInTheDocument();
    expect(
      screen.queryByLabelText("URL"),
    ).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("Command"), "uvx");
    await user.selectOptions(screen.getByLabelText("Transport"), "streamable_http");

    expect(screen.getByLabelText("URL")).toHaveValue("https://mcp.example.com");
    expect(
      screen.queryByLabelText("Command"),
    ).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Transport"), "stdio");
    expect(screen.getByLabelText("Command")).toHaveValue("uvx");
  });

  test("ChatModelForm fills initial values and submits update payload", async () => {
    const user = userEvent.setup();
    mockUpdateChatModel.mutateAsync.mockResolvedValue({ id: "llm-1" });

    render(
      <ChatModelForm
        mode="edit"
        model={{
          id: "llm-1",
          name: "GPT-4.1",
          provider: "openai_compatible",
          model_name: "gpt-4.1",
          base_url: "https://api.example.com",
          description: "chat model",
          temperature: 0.2,
          context_window: 16000,
          support_vision: false,
          support_function_calling: true,
          is_enabled: true,
          is_default: false,
        }}
      />,
    );

    expect(screen.getByLabelText("名称")).toHaveValue("GPT-4.1");
    await user.clear(screen.getByLabelText("Model Name"));
    await user.type(screen.getByLabelText("Model Name"), "gpt-4.1-mini");
    await user.click(screen.getByRole("button", { name: "保存 Chat Model" }));

    await waitFor(() =>
      expect(mockUpdateChatModel.mutateAsync).toHaveBeenCalledWith({
        name: "GPT-4.1",
        provider: "openai_compatible",
        model_name: "gpt-4.1-mini",
        base_url: "https://api.example.com",
        api_key: undefined,
        temperature: 0.2,
        context_window: 16000,
        support_vision: false,
        support_function_calling: true,
        is_enabled: true,
        is_default: false,
        description: "chat model",
      }),
    );
  });

  test("EmbeddingModelForm fills initial values and submits update payload", async () => {
    const user = userEvent.setup();
    mockUpdateEmbeddingModel.mutateAsync.mockResolvedValue({ id: "emb-1" });

    render(
      <EmbeddingModelForm
        mode="edit"
        model={{
          id: "emb-1",
          name: "text-embedding-3-large",
          type: "openai_compatible",
          model_name: "text-embedding-3-large",
          endpoint: "https://api.example.com",
          description: "embedding model",
          batch_size: 16,
          is_enabled: true,
          is_default: false,
        }}
      />,
    );

    expect(screen.getByLabelText("名称")).toHaveValue("text-embedding-3-large");
    await user.clear(screen.getByLabelText("描述"));
    await user.type(screen.getByLabelText("描述"), "updated embedding model");
    await user.click(screen.getByRole("button", { name: "保存 Embedding Model" }));

    await waitFor(() =>
      expect(mockUpdateEmbeddingModel.mutateAsync).toHaveBeenCalledWith({
        name: "text-embedding-3-large",
        type: "openai_compatible",
        model_name: "text-embedding-3-large",
        endpoint: "https://api.example.com",
        api_key: undefined,
        local_model_path: undefined,
        batch_size: 16,
        is_enabled: true,
        is_default: false,
        description: "updated embedding model",
      }),
    );
  });

  test("RerankModelForm fills initial values and submits update payload", async () => {
    const user = userEvent.setup();
    mockUpdateRerankModel.mutateAsync.mockResolvedValue({ id: "rerank-1" });

    render(
      <RerankModelForm
        mode="edit"
        model={{
          id: "rerank-1",
          name: "bge-reranker-v2",
          provider: "dashscope",
          model_name: "bge-reranker-v2",
          base_url: "https://api.example.com",
          description: "rerank model",
          is_enabled: true,
          is_default: false,
        }}
      />,
    );

    expect(screen.getByLabelText("名称")).toHaveValue("bge-reranker-v2");
    await user.clear(screen.getByLabelText("Provider"));
    await user.type(screen.getByLabelText("Provider"), "siliconflow");
    await user.click(screen.getByRole("button", { name: "保存 Rerank Model" }));

    await waitFor(() =>
      expect(mockUpdateRerankModel.mutateAsync).toHaveBeenCalledWith({
        name: "bge-reranker-v2",
        provider: "siliconflow",
        model_name: "bge-reranker-v2",
        base_url: "https://api.example.com",
        api_key: undefined,
        is_enabled: true,
        is_default: false,
        description: "rerank model",
      }),
    );
  });
});
