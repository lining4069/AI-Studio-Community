import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import { KnowledgeBaseDetailRoute } from "@/routes/knowledge-base-detail";

const mockUpdateKnowledgeBase = vi.fn();
const mockRetrieveKnowledgeBase = vi.fn();
const mockKnowledgeBaseChat = vi.fn();

vi.mock("@/api/endpoints/knowledge-base", () => ({
  useKnowledgeBaseDetail: () => ({
    data: {
      id: "kb-1",
      name: "组件设计知识库",
      description: "用于前端组件设计与规范沉淀",
      collection_name: "kb_internal_collection_001",
      embedding_model_id: "embed-model-001",
      rerank_model_id: "rerank-model-001",
      chunk_size: 512,
      chunk_overlap: 50,
      top_k: 5,
      similarity_threshold: 0,
      vector_weight: 0.7,
      enable_rerank: true,
      rerank_top_k: 3,
      updated_at: "2026-04-10T12:00:00Z",
    },
  }),
  useKnowledgeBaseFiles: () => ({ data: [] }),
  useRetrieveKnowledgeBase: () => ({
    mutateAsync: mockRetrieveKnowledgeBase,
    isPending: false,
  }),
  useKnowledgeBaseChat: () => ({
    mutateAsync: mockKnowledgeBaseChat,
    isPending: false,
  }),
  useUploadKnowledgeBaseFile: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useIndexKnowledgeBaseFile: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateKnowledgeBase: () => ({
    mutateAsync: mockUpdateKnowledgeBase,
    isPending: false,
    error: null,
  }),
}));

vi.mock("@/api/endpoints/settings", () => ({
  useChatModels: () => ({ data: [] }),
  useEmbeddingModels: () => ({
    data: [{ id: "embed-model-001", name: "bge-m3 向量模型" }],
  }),
  useRerankModels: () => ({
    data: [{ id: "rerank-model-001", name: "bge-reranker-v2-m3" }],
  }),
}));

function renderRoute() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/knowledge-bases/kb-1"]}>
        <Routes>
          <Route
            path="/knowledge-bases/:kbId"
            element={<KnowledgeBaseDetailRoute />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("KnowledgeBaseDetailRoute overview", () => {
  beforeEach(() => {
    mockUpdateKnowledgeBase.mockReset();
    mockUpdateKnowledgeBase.mockResolvedValue(null);
    mockRetrieveKnowledgeBase.mockReset();
    mockRetrieveKnowledgeBase.mockResolvedValue({
      results: [
        {
          chunk_id: "chunk-001",
          score: 0.9412,
          content: "知识库工作台应当提供正式配置、检索验证与问答验证闭环。",
        },
      ],
    });
    mockKnowledgeBaseChat.mockReset();
    mockKnowledgeBaseChat.mockResolvedValue({
      query: "知识库工作台如何帮助联调",
      answer: "它把配置、文件、检索和问答放在同一个知识库工作台里，便于联调验证。",
      results: [
        {
          chunk_id: "chunk-chat-001",
          score: 0.9032,
          content: "知识库工作台整合了配置、文件管理、检索验证和问答验证。",
        },
      ],
    });
  });

  test(
    "renders a formal overview form and saves knowledge base settings",
    async () => {
      const user = userEvent.setup();

      renderRoute();

    expect(await screen.findByText("Embedding 模型")).toBeInTheDocument();
    expect(screen.getAllByText("bge-m3 向量模型")).toHaveLength(2);
    expect(screen.getByText("Rerank 策略")).toBeInTheDocument();
    expect(screen.getByText("已启用 · bge-reranker-v2-m3")).toBeInTheDocument();
    expect(screen.getByText("切片与召回")).toBeInTheDocument();
    expect(screen.getByText("512 字 / 重叠 50 / Top 5")).toBeInTheDocument();
    expect(screen.queryByText("Collection")).not.toBeInTheDocument();
    expect(screen.queryByText("kb_internal_collection_001")).not.toBeInTheDocument();
    expect(screen.queryByText("embed-model-001")).not.toBeInTheDocument();

    const nameInput = await screen.findByLabelText("知识库名称");
    const descriptionInput = screen.getByLabelText("知识库描述");
    const chunkSizeInput = screen.getByLabelText("Chunk Size");
    const topKInput = screen.getByLabelText("Top K");

    await user.clear(nameInput);
    await user.type(nameInput, "前端工作台知识库");
    await user.clear(descriptionInput);
    await user.type(descriptionInput, "知识库工作台页面设计与联调规范");
    await user.clear(chunkSizeInput);
    await user.type(chunkSizeInput, "640");
    await user.clear(topKInput);
    await user.type(topKInput, "8");

    await user.click(screen.getByRole("button", { name: "保存配置" }));

      expect(mockUpdateKnowledgeBase).toHaveBeenCalledWith({
        name: "前端工作台知识库",
        description: "知识库工作台页面设计与联调规范",
        embedding_model_id: "embed-model-001",
        rerank_model_id: "rerank-model-001",
        chunk_size: 640,
        chunk_overlap: 50,
        top_k: 8,
        similarity_threshold: 0,
        vector_weight: 0.7,
        enable_rerank: true,
        rerank_top_k: 3,
      });
    },
    8000,
  );

  test("renders retrieve results as formal hit cards after search", async () => {
    const user = userEvent.setup();

    renderRoute();

    await user.click(screen.getByRole("tab", { name: "Retrieve" }));
    await user.type(
      screen.getByPlaceholderText("例如：总结这套系统里的 AgentConfig 与 Session 的关系"),
      "知识库工作台如何组织",
    );

    await user.click(screen.getByRole("button", { name: "执行检索" }));

    expect(mockRetrieveKnowledgeBase).toHaveBeenCalledWith({
      query: "知识库工作台如何组织",
      kb_ids: ["kb-1"],
    });
    expect(await screen.findByText("命中片段 1")).toBeInTheDocument();
    expect(screen.getByText("相关度 0.9412")).toBeInTheDocument();
    expect(
      screen.getByText("知识库工作台应当提供正式配置、检索验证与问答验证闭环。"),
    ).toBeInTheDocument();
  });

  test("renders formal rag chat messages and supporting citations", async () => {
    const user = userEvent.setup();

    renderRoute();

    await user.click(screen.getByRole("tab", { name: "Chat" }));
    await user.type(
      screen.getByPlaceholderText(
        "基于当前知识库回答：这个系统中的 Agent 模块是如何组织的？",
      ),
      "知识库工作台如何帮助联调",
    );

    await user.click(screen.getByRole("button", { name: "开始问答" }));

    expect(mockKnowledgeBaseChat).toHaveBeenCalledWith({
      query: "知识库工作台如何帮助联调",
      kb_ids: ["kb-1"],
      llm_model_id: undefined,
    });
    expect(await screen.findByText("用户问题")).toBeInTheDocument();
    expect(screen.getByText("知识库工作台如何帮助联调")).toBeInTheDocument();
    expect(screen.getByText("助手回答")).toBeInTheDocument();
    expect(
      screen.getByText(
        "它把配置、文件、检索和问答放在同一个知识库工作台里，便于联调验证。",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("引用片段 1")).toBeInTheDocument();
    expect(
      screen.getByText("知识库工作台整合了配置、文件管理、检索验证和问答验证。"),
    ).toBeInTheDocument();
  });
});
