import { ArrowRight, Bot, Database, Layers2, Settings2 } from "lucide-react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import { useAgentConfigs } from "@/api/endpoints/agent";
import { useKnowledgeBases } from "@/api/endpoints/knowledge-base";
import { useCurrentUser } from "@/api/endpoints/auth";
import {
  useChatModels,
  useEmbeddingModels,
  useMcpServers,
  useRerankModels,
} from "@/api/endpoints/settings";
import { EmptyState } from "@/components/shared/empty-state";
import { MetricCard } from "@/components/shared/metric-card";
import { SectionHeading } from "@/components/shared/section-heading";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn, formatDate } from "@/lib/utils";

const quickActions = [
  {
    title: "新建知识库",
    description: "从文件、切片与索引开始搭建你的 RAG 资产。",
    icon: Database,
    to: "/knowledge-bases",
  },
  {
    title: "配置助手",
    description: "将模型、工具、MCP 和知识库组装成一个助手。",
    icon: Bot,
    to: "/agents",
  },
  {
    title: "系统配置",
    description: "统一管理 Chat、Embedding、Rerank 与 MCP 资源。",
    icon: Settings2,
    to: "/settings",
  },
];

export function HomeRoute() {
  const currentUser = useCurrentUser();
  const knowledgeBases = useKnowledgeBases();
  const agentConfigs = useAgentConfigs();
  const mcpServers = useMcpServers();
  const chatModels = useChatModels();
  const embeddingModels = useEmbeddingModels();
  const rerankModels = useRerankModels();

  const metrics = [
    {
      label: "知识库",
      value: knowledgeBases.data?.items.length ?? 0,
      description: "已创建的知识库数量，后续可从这里快速进入检索调试与 RAG Chat。",
    },
    {
      label: "助手",
      value: agentConfigs.data?.length ?? 0,
      description: "已经配置好的 AgentConfig 数量，可直接进入详情或新建对话。",
    },
    {
      label: "MCP",
      value: mcpServers.data?.length ?? 0,
      description: "已录入系统配置的 MCP Server，总数会作为首页健康度摘要的一部分。",
    },
    {
      label: "模型能力",
      value:
        (chatModels.data?.length ?? 0) +
        (embeddingModels.data?.length ?? 0) +
        (rerankModels.data?.length ?? 0),
      description: "Chat / Embedding / Rerank 模型资源总和。",
    },
  ];

  return (
    <div className="space-y-8">
      <SectionHeading
        eyebrow="Workspace"
        title="AI Studio 首页"
        description={`这是你的桌面工作台首页：${
          currentUser.data?.nickname ?? currentUser.data?.username ?? "欢迎回来"
        }，这里会汇总最近会话、常用助手、知识库健康度与系统能力摘要。`}
      />

      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.9fr]">
        <Card className="overflow-hidden bg-[linear-gradient(135deg,#0f172a_0%,#0f766e_48%,#e2f3ff_100%)] text-white">
          <CardHeader>
            <p className="text-sm uppercase tracking-[0.28em] text-white/70">
              Cherry-style desktop shell
            </p>
            <CardTitle className="mt-6 max-w-2xl text-4xl leading-tight text-white">
              把知识库、Agent、模型能力和桌面体验收在同一个工作台里。
            </CardTitle>
            <CardDescription className="max-w-2xl text-sm leading-6 text-white/80">
              首页作为工作台总览，不只是跳转页。后续会接入最近会话、常用助手、模型状态与 MCP 健康度。
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-3">
            {[
              { label: "知识库", value: "RAG 内聚工作流" },
              { label: "Agent", value: "配置 + 会话双层心智" },
              { label: "设置", value: "能力配置与账户一体化" },
            ].map((item) => (
              <motion.div
                key={item.label}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
                className="rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur"
              >
                <p className="text-sm text-white/70">{item.label}</p>
                <p className="mt-2 text-lg font-semibold">{item.value}</p>
              </motion.div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>系统快照</CardTitle>
            <CardDescription>第一版首页的核心摘要区。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              [
                "最近知识库",
                knowledgeBases.data?.items[0]
                  ? `${knowledgeBases.data.items[0].name} · 更新于 ${formatDate(
                      knowledgeBases.data.items[0].updated_at,
                    )}`
                  : "还没有知识库，建议先从文档上传开始。",
              ],
              [
                "常用助手",
                agentConfigs.data?.[0]
                  ? `${agentConfigs.data[0].name} · ${agentConfigs.data[0].agent_type}`
                  : "还没有助手，先创建一个 AgentConfig 会更自然。",
              ],
              [
                "系统能力",
                `Chat ${chatModels.data?.length ?? 0} / Embedding ${
                  embeddingModels.data?.length ?? 0
                } / Rerank ${rerankModels.data?.length ?? 0}`,
              ],
            ].map(([title, desc]) => (
              <div key={title} className="rounded-2xl bg-slate-50 p-4">
                <p className="font-medium text-slate-950">{title}</p>
                <p className="mt-2 text-sm leading-6 text-slate-500">{desc}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {quickActions.map((action) => {
          const Icon = action.icon;

          return (
            <Card key={action.title}>
              <CardHeader>
                <div className="flex size-12 items-center justify-center rounded-2xl bg-sky-50 text-sky-600">
                  <Icon className="size-6" />
                </div>
                <CardTitle className="mt-5">{action.title}</CardTitle>
                <CardDescription>{action.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Link
                  to={action.to}
                  className={cn(
                    buttonVariants({ variant: "ghost" }),
                    "h-auto justify-start px-0 text-sky-600 hover:bg-transparent",
                  )}
                >
                  进入模块
                  <ArrowRight className="ml-2 size-4" />
                </Link>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        {metrics.map((item) => (
          <MetricCard
            key={item.label}
            label={item.label}
            value={item.value}
            description={item.description}
          />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>常用助手</CardTitle>
            <CardDescription>从首页直接进入配置页或开始新对话。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {agentConfigs.data?.length ? (
              agentConfigs.data.slice(0, 4).map((agent) => (
                <Link
                  key={agent.id}
                  to={`/agents/${agent.id}`}
                  className="block rounded-2xl border border-slate-200 p-4 transition hover:border-sky-200 hover:bg-sky-50/40"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="font-medium text-slate-950">{agent.name}</p>
                      <p className="mt-1 text-sm text-slate-500">
                        {agent.agent_type} · max_loop {agent.max_loop}
                      </p>
                    </div>
                    <ArrowRight className="size-4 text-slate-400" />
                  </div>
                </Link>
              ))
            ) : (
              <EmptyState
                title="还没有助手"
                description="创建第一个 AgentConfig 后，这里会展示最近活跃或常用的助手。"
                action={
                  <Link className={buttonVariants()} to="/agents">
                    去创建助手
                  </Link>
                }
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>知识库概览</CardTitle>
            <CardDescription>快速查看最近更新的知识库并进入详情工作区。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {knowledgeBases.data?.items.length ? (
              knowledgeBases.data.items.slice(0, 4).map((kb) => (
                <Link
                  key={kb.id}
                  to={`/knowledge-bases/${kb.id}`}
                  className="block rounded-2xl border border-slate-200 p-4 transition hover:border-emerald-200 hover:bg-emerald-50/40"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="font-medium text-slate-950">{kb.name}</p>
                      <p className="mt-1 text-sm text-slate-500">
                        top_k {kb.top_k} · {kb.is_active ? "已启用" : "未启用"}
                      </p>
                    </div>
                    <ArrowRight className="size-4 text-slate-400" />
                  </div>
                </Link>
              ))
            ) : (
              <EmptyState
                title="还没有知识库"
                description="先创建知识库并上传文件，首页就能展示最近更新的 RAG 资产。"
                action={
                  <Link className={buttonVariants()} to="/knowledge-bases">
                    去创建知识库
                  </Link>
                }
              />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>工作台里程碑</CardTitle>
          <CardDescription>当前实现优先保证信息架构、页面骨架与 API 接入边界稳定。</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-4">
          {[
            "认证与 AppShell",
            "知识库工作流",
            "Agent 配置与聊天",
            "系统配置中心",
          ].map((item) => (
            <div key={item} className="rounded-2xl border border-slate-200 p-4">
              <div className="flex items-center gap-3">
                <Layers2 className="size-5 text-sky-600" />
                <p className="font-medium text-slate-900">{item}</p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
