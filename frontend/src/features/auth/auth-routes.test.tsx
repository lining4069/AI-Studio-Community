import { screen } from "@testing-library/react";

import { appRoutes } from "@/app/router";
import { renderRouter } from "@/test/render-router";

describe("auth routes", () => {
  test("login route renders the actual login form", async () => {
    renderRouter(appRoutes, ["/login"]);

    expect(await screen.findByRole("heading", { name: "欢迎回来" })).toBeInTheDocument();
    expect(screen.getByLabelText("用户名")).toBeInTheDocument();
    expect(screen.getByLabelText("密码")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "登录" })).toBeInTheDocument();
  });

  test("register route renders the actual register form", async () => {
    renderRouter(appRoutes, ["/register"]);

    expect(
      await screen.findByRole("heading", { name: "开始构建你的 AI 工作台" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("用户名")).toBeInTheDocument();
    expect(screen.getByLabelText("密码")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建账号" })).toBeInTheDocument();
  });
});
