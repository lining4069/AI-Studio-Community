import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { apiClient } from "@/api/client";
import { useSessions } from "@/api/endpoints/agent";

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
