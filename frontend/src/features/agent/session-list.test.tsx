import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { SessionList } from "@/features/agent/session-list";

const mockRefresh = vi.fn();
const mockOpenSession = vi.fn();
const mockCreateSession = vi.fn();

const sessions = [
  {
    id: "sess-1",
    user_id: 1,
    config_id: "cfg-1",
    title: "调研 Tavily MCP 接入",
    summary: null,
    latest_message_preview: "请帮我检查 Tavily MCP 的 streamable_http 接入链路。",
    created_at: "2026-04-13T08:00:00Z",
    updated_at: "2026-04-13T09:30:00Z",
  },
  {
    id: "sess-2",
    user_id: 1,
    config_id: "cfg-1",
    title: "梳理 Agent Session 工作流",
    summary: "已生成摘要",
    latest_message_preview: null,
    created_at: "2026-04-12T10:00:00Z",
    updated_at: "2026-04-12T11:00:00Z",
  },
];

describe("SessionList", () => {
  beforeEach(() => {
    mockRefresh.mockReset();
    mockOpenSession.mockReset();
    mockCreateSession.mockReset();
  });

  test("renders session cards and supports refresh/open actions", async () => {
    const user = userEvent.setup();

    render(
      <SessionList
        sessions={sessions}
        onRefresh={mockRefresh}
        onOpenSession={mockOpenSession}
        onCreateSession={mockCreateSession}
      />,
    );

    expect(screen.getByText("会话工作区")).toBeInTheDocument();
    expect(screen.getByText("共 2 个历史会话")).toBeInTheDocument();
    expect(screen.getByText("调研 Tavily MCP 接入")).toBeInTheDocument();
    expect(screen.getByText("梳理 Agent Session 工作流")).toBeInTheDocument();
    expect(
      screen.getByText("请帮我检查 Tavily MCP 的 streamable_http 接入链路。"),
    ).toBeInTheDocument();
    expect(screen.getByText("当前会话还没有沉淀消息摘要。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "刷新会话列表" }));
    expect(mockRefresh).toHaveBeenCalledTimes(1);

    await user.click(screen.getAllByRole("button", { name: "继续对话" })[0]);
    expect(mockOpenSession).toHaveBeenCalledWith("sess-1");
  });
});
