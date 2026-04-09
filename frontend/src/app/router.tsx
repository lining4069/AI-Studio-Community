import { Navigate, type RouteObject } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGuard } from "@/app/auth-guard";
import { AgentDetailRoute } from "@/routes/agent-detail";
import { AgentsRoute } from "@/routes/agents";
import { ChatRoute } from "@/routes/chat";
import { HomeRoute } from "@/routes/home";
import { KnowledgeBaseDetailRoute } from "@/routes/knowledge-base-detail";
import { KnowledgeBasesRoute } from "@/routes/knowledge-bases";
import { LoginRoute } from "@/routes/login";
import { RegisterRoute } from "@/routes/register";
import { SettingsRoute } from "@/routes/settings";

export const appRoutes: RouteObject[] = [
  {
    path: "/login",
    element: <LoginRoute />,
  },
  {
    path: "/register",
    element: <RegisterRoute />,
  },
  {
    path: "/",
    element: <AuthGuard />,
    children: [
      {
        element: <AppShell />,
        children: [
          {
            index: true,
            element: <Navigate to="/home" replace />,
          },
          {
            path: "/home",
            element: <HomeRoute />,
          },
          {
            path: "/knowledge-bases",
            element: <KnowledgeBasesRoute />,
          },
          {
            path: "/knowledge-bases/:kbId",
            element: <KnowledgeBaseDetailRoute />,
          },
          {
            path: "/agents",
            element: <AgentsRoute />,
          },
          {
            path: "/agents/:configId",
            element: <AgentDetailRoute />,
          },
          {
            path: "/chat/:sessionId",
            element: <ChatRoute />,
          },
          {
            path: "/settings",
            element: <SettingsRoute />,
          },
          {
            path: "/settings/:section/*",
            element: <SettingsRoute />,
          },
        ],
      },
    ],
  },
];
