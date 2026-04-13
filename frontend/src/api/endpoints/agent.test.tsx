import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { apiClient } from "@/api/client";
import { runAgentStream, useSessions } from "@/api/endpoints/agent";

vi.mock("@/api/client", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("useSessions", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
  });

  test("requests filtered sessions for an agent config", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      code: 200,
      message: "Success Response",
      data: {
        items: [
          {
            id: "sess-1",
            user_id: 1,
            config_id: "cfg-1",
            title: "默认会话",
            summary: null,
            created_at: "2026-04-13T10:00:00Z",
            updated_at: "2026-04-13T10:00:00Z",
          },
        ],
      },
    });

    const { result } = renderHook(() => useSessions("cfg-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiClient.get).toHaveBeenCalledWith(
      "/v1/agent/sessions?page=1&page_size=20&config_id=cfg-1",
    );
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0]?.id).toBe("sess-1");
  });
});

describe("runAgentStream", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  test("posts a streaming run request and forwards parsed events", async () => {
    window.localStorage.setItem("ai-studio.access-token", "token-123");
    window.localStorage.setItem("ai-studio.refresh-token", "refresh-123");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              [
                'event: step_start',
                'data: {"step_index":0,"name":"意图理解"}',
                "",
                'event: run_end',
                'data: {"output":"完成"}',
                "",
              ].join("\n"),
            ),
          );
          controller.close();
        },
      }),
    });

    vi.stubGlobal("fetch", fetchMock);

    const events: Array<{ event: string; data: Record<string, unknown> }> = [];
    await runAgentStream("sess-1", {
      payload: {
        input: "帮我分析当前助手能力",
        stream: true,
        debug: false,
        mcp_server_ids: [],
      },
      onEvent: (event) => {
        events.push(event);
      },
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/v1/agent/sessions/sess-1/runs",
      expect.objectContaining({
        method: "POST",
        headers: expect.any(Headers),
      }),
    );
    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer token-123");
    expect(events).toEqual([
      {
        event: "step_start",
        data: { step_index: 0, name: "意图理解" },
      },
      {
        event: "run_end",
        data: { output: "完成" },
      },
    ]);
  });
});
