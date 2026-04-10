import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { appRoutes } from "@/app/router";
import { renderRouter } from "@/test/render-router";

const mockMutateAsync = vi.fn();

vi.mock("@/api/endpoints/auth", async () => {
  const actual = await vi.importActual<typeof import("@/api/endpoints/auth")>(
    "@/api/endpoints/auth",
  );

  return {
    ...actual,
    useCurrentUser: () => ({
      data: {
        id: 1,
        username: "lining",
        nickname: "李宁",
      },
    }),
    useLogout: () => ({
      isPending: false,
      mutateAsync: mockMutateAsync,
    }),
  };
});

describe("AppShell logout", () => {
  beforeEach(() => {
    window.localStorage.setItem("ai-studio.access-token", "access-token");
    window.localStorage.setItem("ai-studio.refresh-token", "refresh-token");
    mockMutateAsync.mockReset();
    mockMutateAsync.mockResolvedValue(null);
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  test("logs out from the app shell and redirects to login", async () => {
    const user = userEvent.setup();

    renderRouter(appRoutes, ["/home"]);

    await user.click(await screen.findByRole("button", { name: "退出登录" }));

    expect(mockMutateAsync).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "欢迎回来" })).toBeInTheDocument();
    });
  });
});
