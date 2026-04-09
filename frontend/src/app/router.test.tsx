import { screen } from "@testing-library/react";

import { appRoutes } from "@/app/router";
import { renderRouter } from "@/test/render-router";

describe("appRoutes", () => {
  it("renders the login page on /login", () => {
    renderRouter(appRoutes, ["/login"]);

    expect(
      screen.getByRole("heading", { name: /欢迎回来/i }),
    ).toBeInTheDocument();
  });
});
