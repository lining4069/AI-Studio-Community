import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { act } from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { ChatRoute } from "@/routes/chat";

const { mockRunAgent, mockRunAgentStream, mockNavigate } = vi.hoisted(() => ({
  mockRunAgent: vi.fn(),
  mockRunAgentStream: vi.fn(),
  mockNavigate: vi.fn(),
}));
let mockMessages: Array<{
  id: string;
  role: string;
  content: string;
  created_at: string;
}> = [];

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );

  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("@/api/endpoints/agent", () => ({
  useAgentConfigDetail: () => ({
    data: {
      id: "cfg-1",
      name: "研究助手",
      description: "负责 MCP、RAG 与系统设计调研",
    },
  }),
  useRunAgent: () => ({
    mutateAsync: mockRunAgent,
    isPending: false,
  }),
  runAgentStream: mockRunAgentStream,
  useSessionDetail: () => ({
    data: {
      id: "sess-1",
      config_id: "cfg-1",
      title: "调研 Agent 工作流",
      created_at: "2026-04-13T12:00:00Z",
      updated_at: "2026-04-13T13:00:00Z",
    },
  }),
  useSessionMessages: () => ({
    data: mockMessages,
  }),
  useSessionSteps: () => ({
    data: [
      {
        id: "step-1",
        step_index: 0,
        type: "think",
        name: "意图理解",
        status: "success",
        output: "识别到用户在询问助手能力概览",
        created_at: "2026-04-13T12:10:05Z",
      },
      {
        id: "step-2",
        step_index: 1,
        type: "tool",
        name: "rag_retrieval",
        status: "success",
        output: "检索到 3 个关联片段",
        created_at: "2026-04-13T12:10:06Z",
      },
    ],
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
      <MemoryRouter initialEntries={["/chat/sess-1"]}>
        <Routes>
          <Route path="/chat/:sessionId" element={<ChatRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ChatRoute formal workspace", () => {
  beforeEach(() => {
    mockRunAgent.mockReset();
    mockRunAgentStream.mockReset();
    mockNavigate.mockReset();
    mockMessages = [
      {
        id: "msg-1",
        role: "user",
        content: "请总结当前助手的能力组成",
        created_at: "2026-04-13T12:10:00Z",
      },
      {
        id: "msg-2",
        role: "assistant",
        content: "当前助手具备模型接入、知识库检索、工具调用和 MCP 扩展能力。",
        created_at: "2026-04-13T12:10:08Z",
      },
    ];
    mockRunAgent.mockResolvedValue({
      session_id: "sess-1",
      output: "已经开始执行新的分析任务。",
      finished: true,
      summary: null,
      steps: [],
    });
    mockRunAgentStream.mockImplementation(async (_sessionId, options) => {
      options.onEvent({
        event: "step_start",
        data: {
          step_id: "stream-step-1",
          step_index: 2,
          type: "tool",
          name: "mcp_search",
          status: "running",
        },
      });
      options.onEvent({
        event: "content",
        data: {
          content: "这是流式返回中的助手回答片段。",
        },
      });
      options.onEvent({
        event: "step_end",
        data: {
          step_id: "stream-step-1",
          step_index: 2,
          status: "success",
          output: "已获取最新搜索结果",
        },
      });
      mockMessages = [
        ...mockMessages,
        {
          id: "msg-3",
          role: "assistant",
          content: "这是流式返回中的助手回答片段。",
          created_at: "2026-04-13T12:11:00Z",
        },
      ];
      options.onEvent({
        event: "run_end",
        data: {
          run_id: "run-1",
          output: "已经开始执行新的分析任务。",
        },
      });
    });
  });

  test("prefers streaming run and updates steps in real time", async () => {
    const user = userEvent.setup();

    renderRoute();

    expect(
      screen.getByRole("heading", { name: "调研 Agent 工作流" }),
    ).toBeInTheDocument();
    expect(screen.getByText("用户消息")).toBeInTheDocument();
    expect(screen.getByText("助手回答")).toBeInTheDocument();
    expect(screen.getByText("当前助手")).toBeInTheDocument();
    expect(screen.getByText("研究助手")).toBeInTheDocument();
    expect(
      screen.getByText("当前助手具备模型接入、知识库检索、工具调用和 MCP 扩展能力。"),
    ).toBeInTheDocument();
    expect(screen.getByText("本次执行步骤")).toBeInTheDocument();
    expect(screen.getByText("意图理解")).toBeInTheDocument();
    expect(screen.getByText("rag_retrieval")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "返回助手详情" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "返回助手详情" }));
    expect(mockNavigate).toHaveBeenCalledWith("/agents/cfg-1");

    await user.type(
      screen.getByPlaceholderText("继续向当前助手提问..."),
      "继续分析当前配置",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() =>
      expect(mockRunAgentStream).toHaveBeenCalledWith("sess-1", {
        onEvent: expect.any(Function),
        payload: {
          input: "继续分析当前配置",
          stream: true,
          debug: false,
          mcp_server_ids: [],
        },
      }),
    );
    expect(mockRunAgent).not.toHaveBeenCalled();
    expect(screen.getByText("mcp_search")).toBeInTheDocument();
    expect(screen.getByText("已获取最新搜索结果")).toBeInTheDocument();
    expect(
      screen.getAllByText("这是流式返回中的助手回答片段。").length,
    ).toBeGreaterThan(0);
    await act(async () => {
      await Promise.resolve();
    });
    await waitFor(() =>
      expect(
        screen.getAllByText("这是流式返回中的助手回答片段。"),
      ).toHaveLength(1),
    );
  });

  test("fills and focuses composer after picking a starter prompt", async () => {
    mockMessages = [];
    const user = userEvent.setup();

    renderRoute();

    const suggestion = screen.getByRole("button", {
      name: "先帮我总结当前助手的能力边界",
    });

    await user.click(suggestion);

    const textarea = screen.getByPlaceholderText("继续向当前助手提问...");
    expect(textarea).toHaveValue("先帮我总结当前助手的能力边界");
    expect(textarea).toHaveFocus();
  });
});
