import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useBuiltinTools } from "@/api/endpoints/agent";
import type {
  AgentMCPServerResponse,
  EmbeddingModelResponse,
  LlmModelResponse,
  RerankModelResponse,
} from "@/api/types";
import {
  useChatModels,
  useEmbeddingModels,
  useMcpServers,
  useRerankModels,
} from "@/api/endpoints/settings";
import { useUserProfile } from "@/api/endpoints/user";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/shared/empty-state";
import { SectionHeading } from "@/components/shared/section-heading";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  ChatModelForm,
  EmbeddingModelForm,
  McpServerForm,
  ProfileForm,
  RerankModelForm,
} from "@/features/settings/forms";
import { formatDate } from "@/lib/utils";

const settingsTabs = {
  account: "/settings/account",
  mcp: "/settings/mcp-servers",
  "chat-models": "/settings/models/chat",
  "embedding-models": "/settings/models/embedding",
  "rerank-models": "/settings/models/rerank",
  tools: "/settings/tools",
} as const;

type SettingsDialogState =
  | { type: "mcp"; mode: "create"; item?: null }
  | { type: "mcp"; mode: "edit"; item: AgentMCPServerResponse }
  | { type: "chat-models"; mode: "create"; item?: null }
  | { type: "chat-models"; mode: "edit"; item: LlmModelResponse }
  | { type: "embedding-models"; mode: "create"; item?: null }
  | { type: "embedding-models"; mode: "edit"; item: EmbeddingModelResponse }
  | { type: "rerank-models"; mode: "create"; item?: null }
  | { type: "rerank-models"; mode: "edit"; item: RerankModelResponse };

export function SettingsRoute() {
  const location = useLocation();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<SettingsDialogState | null>(null);
  const profile = useUserProfile();
  const mcpServers = useMcpServers();
  const chatModels = useChatModels();
  const embeddingModels = useEmbeddingModels();
  const rerankModels = useRerankModels();
  const builtinTools = useBuiltinTools();

  const currentTab = useMemo(() => {
    if (location.pathname.includes("/settings/mcp-servers")) return "mcp";
    if (location.pathname.includes("/settings/models/chat")) return "chat-models";
    if (location.pathname.includes("/settings/models/embedding")) return "embedding-models";
    if (location.pathname.includes("/settings/models/rerank")) return "rerank-models";
    if (location.pathname.includes("/settings/tools")) return "tools";
    return "account";
  }, [location.pathname]);

  return (
    <div className="space-y-8">
      <SectionHeading
        eyebrow="Settings"
        title="系统配置"
        description="系统配置统一管理能力配置与账户设置，第一版覆盖 MCP、模型与内置工具目录。"
      />

      <Tabs
        value={currentTab}
        onValueChange={(value) =>
          navigate(settingsTabs[value as keyof typeof settingsTabs] ?? "/settings/account")
        }
      >
        <TabsList>
          <TabsTrigger value="account">账户</TabsTrigger>
          <TabsTrigger value="mcp">MCP Servers</TabsTrigger>
          <TabsTrigger value="chat-models">Chat Models</TabsTrigger>
          <TabsTrigger value="embedding-models">Embedding</TabsTrigger>
          <TabsTrigger value="rerank-models">Rerank</TabsTrigger>
          <TabsTrigger value="tools">内置工具</TabsTrigger>
        </TabsList>
        <TabsContent value="account">
          <Card>
            <CardHeader>
              <CardTitle>账户设置</CardTitle>
              <CardDescription>个人信息、密码与头像设置的第一版先收敛到个人资料编辑。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-3">
                {[
                  ["用户名", profile.data?.username ?? "--"],
                  ["状态", profile.data?.is_active ? "已启用" : "已停用"],
                  ["超级用户", profile.data?.is_superuser ? "是" : "否"],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-2xl bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-600">
                      {label}
                    </p>
                    <p className="mt-3 font-medium text-slate-950">{value}</p>
                  </div>
                ))}
              </div>
              <ProfileForm
                initialValues={{
                  nickname: profile.data?.nickname ?? "",
                  email: profile.data?.email ?? "",
                  bio: profile.data?.bio ?? "",
                }}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="mcp">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle>MCP Servers</CardTitle>
                <CardDescription>管理 streamable_http、stdio、sse 等 MCP 配置。</CardDescription>
              </div>
              <Dialog
                open={dialog?.type === "mcp"}
                onOpenChange={(open) => {
                  if (!open) {
                    setDialog(null);
                  }
                }}
              >
                <DialogTrigger asChild>
                  <Button onClick={() => setDialog({ type: "mcp", mode: "create" })}>新增 MCP</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>
                      {dialog?.type === "mcp" && dialog.mode === "edit"
                        ? "编辑 MCP Server"
                        : "新增 MCP Server"}
                    </DialogTitle>
                    <DialogDescription>支持 streamable_http、stdio 与 sse 三类 transport。</DialogDescription>
                  </DialogHeader>
                  <McpServerForm
                    mode={dialog?.type === "mcp" ? dialog.mode : "create"}
                    server={dialog?.type === "mcp" && dialog.mode === "edit" ? dialog.item : null}
                    onSuccess={() => setDialog(null)}
                  />
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent className="space-y-3">
              {mcpServers.data?.length ? (
                mcpServers.data.map((server) => (
                  <div key={server.id} className="rounded-2xl border border-slate-200 p-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <p className="font-medium text-slate-950">{server.name}</p>
                        <p className="mt-1 text-sm text-slate-500">
                          {server.transport} · {server.enabled ? "已启用" : "已禁用"} · 更新于{" "}
                          {formatDate(server.updated_at)}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
                          {server.url || server.command || "未配置入口"}
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setDialog({ type: "mcp", mode: "edit", item: server })}
                        >
                          编辑 MCP
                        </Button>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState
                  title="还没有 MCP Server"
                  description="先把 Tavily、uvx 或本地 Python stdio server 录入进来，后续才能在 Agent 详情页里关联。"
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="chat-models">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle>Chat Models</CardTitle>
                <CardDescription>管理聊天模型与默认模型。</CardDescription>
              </div>
              <Dialog
                open={dialog?.type === "chat-models"}
                onOpenChange={(open) => {
                  if (!open) {
                    setDialog(null);
                  }
                }}
              >
                <DialogTrigger asChild>
                  <Button onClick={() => setDialog({ type: "chat-models", mode: "create" })}>
                    新增 Chat Model
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>
                      {dialog?.type === "chat-models" && dialog.mode === "edit"
                        ? "编辑 Chat Model"
                        : "新增 Chat Model"}
                    </DialogTitle>
                    <DialogDescription>第一版先覆盖 OpenAI Compatible / DashScope 一类配置。</DialogDescription>
                  </DialogHeader>
                  <ChatModelForm
                    mode={dialog?.type === "chat-models" ? dialog.mode : "create"}
                    model={
                      dialog?.type === "chat-models" && dialog.mode === "edit" ? dialog.item : null
                    }
                    onSuccess={() => setDialog(null)}
                  />
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent className="space-y-3">
              {chatModels.data?.length ? (
                chatModels.data.map((model) => (
                  <div key={model.id} className="rounded-2xl border border-slate-200 p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-medium text-slate-950">{model.name}</p>
                        <p className="mt-1 text-sm text-slate-500">
                          {model.provider} · {model.model_name} · {model.is_default ? "默认模型" : "普通模型"}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setDialog({ type: "chat-models", mode: "edit", item: model })}
                      >
                        编辑 Chat Model
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState title="还没有 Chat Model" description="创建后即可在知识库问答和 Agent 基础配置里选择模型。" />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="embedding-models">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle>Embedding Models</CardTitle>
                <CardDescription>管理向量嵌入模型。</CardDescription>
              </div>
              <Dialog
                open={dialog?.type === "embedding-models"}
                onOpenChange={(open) => {
                  if (!open) {
                    setDialog(null);
                  }
                }}
              >
                <DialogTrigger asChild>
                  <Button onClick={() => setDialog({ type: "embedding-models", mode: "create" })}>
                    新增 Embedding Model
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>
                      {dialog?.type === "embedding-models" && dialog.mode === "edit"
                        ? "编辑 Embedding Model"
                        : "新增 Embedding Model"}
                    </DialogTitle>
                    <DialogDescription>支持 OpenAI Compatible 或本地模型两类接入方式。</DialogDescription>
                  </DialogHeader>
                  <EmbeddingModelForm
                    mode={dialog?.type === "embedding-models" ? dialog.mode : "create"}
                    model={
                      dialog?.type === "embedding-models" && dialog.mode === "edit"
                        ? dialog.item
                        : null
                    }
                    onSuccess={() => setDialog(null)}
                  />
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent className="space-y-3">
              {embeddingModels.data?.length ? (
                embeddingModels.data.map((model) => (
                  <div key={model.id} className="rounded-2xl border border-slate-200 p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-medium text-slate-950">{model.name}</p>
                        <p className="mt-1 text-sm text-slate-500">
                          {model.type} · {model.model_name || model.local_model_path || "待补充"} ·{" "}
                          {model.is_default ? "默认" : "普通"}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setDialog({ type: "embedding-models", mode: "edit", item: model })
                        }
                      >
                        编辑 Embedding Model
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState title="还没有 Embedding Model" description="知识库创建和索引会依赖 Embedding Model 资源。" />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="rerank-models">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle>Rerank Models</CardTitle>
                <CardDescription>管理重排模型。</CardDescription>
              </div>
              <Dialog
                open={dialog?.type === "rerank-models"}
                onOpenChange={(open) => {
                  if (!open) {
                    setDialog(null);
                  }
                }}
              >
                <DialogTrigger asChild>
                  <Button onClick={() => setDialog({ type: "rerank-models", mode: "create" })}>
                    新增 Rerank Model
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>
                      {dialog?.type === "rerank-models" && dialog.mode === "edit"
                        ? "编辑 Rerank Model"
                        : "新增 Rerank Model"}
                    </DialogTitle>
                    <DialogDescription>用于提升 Retrieval 和 RAG Chat 的重排质量。</DialogDescription>
                  </DialogHeader>
                  <RerankModelForm
                    mode={dialog?.type === "rerank-models" ? dialog.mode : "create"}
                    model={
                      dialog?.type === "rerank-models" && dialog.mode === "edit" ? dialog.item : null
                    }
                    onSuccess={() => setDialog(null)}
                  />
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent className="space-y-3">
              {rerankModels.data?.length ? (
                rerankModels.data.map((model) => (
                  <div key={model.id} className="rounded-2xl border border-slate-200 p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-medium text-slate-950">{model.name}</p>
                        <p className="mt-1 text-sm text-slate-500">
                          {model.provider} · {model.model_name || "待补充"} · {model.is_default ? "默认" : "普通"}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setDialog({ type: "rerank-models", mode: "edit", item: model })}
                      >
                        编辑 Rerank Model
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState title="还没有 Rerank Model" description="如果知识库需要重排能力，可以先在这里补充模型资源。" />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tools">
          <Card>
            <CardHeader>
              <CardTitle>内置工具目录</CardTitle>
              <CardDescription>当前后端仅提供只读目录，所以这一页用于浏览能力和输入 schema。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {builtinTools.data?.length ? (
                builtinTools.data.map((tool) => (
                  <div key={tool.name} className="rounded-2xl border border-slate-200 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="font-medium text-slate-950">{tool.name}</p>
                        <p className="mt-1 text-sm text-slate-500">{tool.description}</p>
                      </div>
                      <p className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                        {tool.has_config ? "支持配置" : "免配置"}
                      </p>
                    </div>
                    <pre className="mt-4 overflow-auto rounded-2xl bg-slate-50 p-4 text-xs leading-6 text-slate-600">
                      {JSON.stringify(tool.input_schema, null, 2)}
                    </pre>
                  </div>
                ))
              ) : (
                <EmptyState title="未读取到内置工具目录" description="确认后端 `/v1/agent/builtin-tools` 可访问后，这里会展示工具清单和 schema。" />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
