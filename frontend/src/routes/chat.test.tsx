import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { ChatRoute } from "@/routes/chat";

const mockRunAgent = vi.fn();

vi.mock("@/api/endpoints/agent", () => ({
  useRunAgent: () => ({
    mutateAsync: mockRunAgent,
    isPending: false,
  }),
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
    data: [
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
    ],
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
    mockRunAgent.mockResolvedValue({
      session_id: "sess-1",
      output: "已经开始执行新的分析任务。",
      finished: true,
      summary: null,
      steps: [],
    });
  });

  test("renders formal message stream and run panel, then sends a prompt", async () => {
    const user = userEvent.setup();

    renderRoute();

    expect(
      screen.getByRole("heading", { name: "调研 Agent 工作流" }),
    ).toBeInTheDocument();
    expect(screen.getByText("用户消息")).toBeInTheDocument();
    expect(screen.getByText("助手回答")).toBeInTheDocument();
    expect(
      screen.getByText("当前助手具备模型接入、知识库检索、工具调用和 MCP 扩展能力。"),
    ).toBeInTheDocument();
    expect(screen.getByText("本次执行步骤")).toBeInTheDocument();
    expect(screen.getByText("意图理解")).toBeInTheDocument();
    expect(screen.getByText("rag_retrieval")).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText("继续向当前助手提问..."),
      "继续分析当前配置",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() =>
      expect(mockRunAgent).toHaveBeenCalledWith({
        input: "继续分析当前配置",
        stream: false,
        debug: false,
        mcp_server_ids: [],
      }),
    );
  });
});
