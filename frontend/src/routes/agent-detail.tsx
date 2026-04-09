import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import {
  useAddAgentTool,
  useAgentConfigDetail,
  useCreateSession,
  useLinkAgentKb,
  useLinkAgentMcp,
  useRemoveAgentTool,
  useUnlinkAgentKb,
  useUnlinkAgentMcp,
  useUpdateAgentConfig,
  useBuiltinTools,
} from "@/api/endpoints/agent";
import { useKnowledgeBases } from "@/api/endpoints/knowledge-base";
import { useChatModels, useMcpServers } from "@/api/endpoints/settings";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { SectionHeading } from "@/components/shared/section-heading";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { createAgentSchema } from "@/lib/validators/agent";

export function AgentDetailRoute() {
  const navigate = useNavigate();
  const { configId } = useParams();
  const detail = useAgentConfigDetail(configId);
  const builtinTools = useBuiltinTools();
  const knowledgeBases = useKnowledgeBases();
  const mcpServers = useMcpServers();
  const chatModels = useChatModels();

  const updateConfig = useUpdateAgentConfig(configId);
  const addTool = useAddAgentTool(configId);
  const removeTool = useRemoveAgentTool(configId);
  const linkMcp = useLinkAgentMcp(configId);
  const unlinkMcp = useUnlinkAgentMcp(configId);
  const linkKb = useLinkAgentKb(configId);
  const unlinkKb = useUnlinkAgentKb(configId);
  const createSession = useCreateSession();

  const form = useForm<
    z.input<typeof createAgentSchema>,
    unknown,
    z.output<typeof createAgentSchema>
  >({
    resolver: zodResolver(createAgentSchema),
    defaultValues: {
      name: "",
      description: "",
      llm_model_id: "",
      agent_type: "simple",
      max_loop: 5,
      system_prompt: "",
      enabled: true,
    },
  });

  useEffect(() => {
    if (!detail.data) {
      return;
    }

    form.reset({
      name: detail.data.name,
      description: detail.data.description ?? "",
      llm_model_id: detail.data.llm_model_id ?? "",
      agent_type: detail.data.agent_type,
      max_loop: detail.data.max_loop,
      system_prompt: detail.data.system_prompt ?? "",
      enabled: detail.data.enabled,
    });
  }, [detail.data, form]);

  const linkedToolNames = useMemo(
    () => new Set(detail.data?.tools?.map((tool) => tool.tool_name) ?? []),
    [detail.data?.tools],
  );
  const linkedKbIds = useMemo(
    () => new Set(detail.data?.kbs?.map((item) => item.kb_id) ?? []),
    [detail.data?.kbs],
  );
  const linkedMcpIds = useMemo(
    () => new Set(detail.data?.mcp_servers?.map((item) => item.mcp_server_id) ?? []),
    [detail.data?.mcp_servers],
  );

  const onSubmit = form.handleSubmit(async (values) => {
    await updateConfig.mutateAsync({
      name: values.name,
      description: values.description || undefined,
      llm_model_id: values.llm_model_id || undefined,
      agent_type: values.agent_type,
      max_loop: values.max_loop,
      system_prompt: values.system_prompt || undefined,
      enabled: values.enabled,
    });
  });

  const handleNewSession = async () => {
    if (!configId) {
      return;
    }

    const session = await createSession.mutateAsync({
      config_id: configId,
      title: "默认会话",
    });

    navigate(`/chat/${session.id}`);
  };

  return (
    <div className="space-y-8">
      <SectionHeading
        eyebrow="Agent Detail"
        title={detail.data?.name ?? "助手详情"}
        description={
          detail.data?.description ??
          "助手详情页围绕 AgentConfig 展开，通过多 tab 编辑基础配置、Tools、MCP 与 KB，并提供新建对话入口。"
        }
        actions={
          <Button onClick={handleNewSession} disabled={createSession.isPending}>
            新建对话
          </Button>
        }
      />

      <Tabs defaultValue="base">
        <TabsList>
          <TabsTrigger value="base">基础配置</TabsTrigger>
          <TabsTrigger value="tools">Tools</TabsTrigger>
          <TabsTrigger value="mcp">MCP</TabsTrigger>
          <TabsTrigger value="kb">KB</TabsTrigger>
        </TabsList>
        {[
          ["base", "基础配置", "配置名称、模型、agent_type、system prompt 与 max_loop。"],
          ["tools", "内置工具", "启用与配置 calculator、datetime、rag_retrieval 等内置工具。"],
          ["mcp", "MCP", "选择已创建的 MCP Server 并绑定到当前 AgentConfig。"],
          ["kb", "知识库", "选择一个或多个知识库作为助手的默认检索资源。"],
        ].map(([value, title, desc]) => (
          <TabsContent key={value} value={value}>
            {value === "base" ? (
              <Card>
                <CardHeader>
                  <CardTitle>{title}</CardTitle>
                  <CardDescription>{desc}</CardDescription>
                </CardHeader>
                <CardContent>
                  <form className="space-y-4" onSubmit={onSubmit}>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="detail-agent-name">名称</Label>
                        <Input id="detail-agent-name" {...form.register("name")} />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="detail-agent-llm-model">Chat Model</Label>
                        <select
                          id="detail-agent-llm-model"
                          className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-sky-500"
                          {...form.register("llm_model_id")}
                        >
                          <option value="">暂不绑定</option>
                          {chatModels.data?.map((model) => (
                            <option key={model.id} value={model.id}>
                              {model.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="detail-agent-type">Agent 类型</Label>
                        <select
                          id="detail-agent-type"
                          className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-sky-500"
                          {...form.register("agent_type")}
                        >
                          <option value="simple">simple</option>
                          <option value="react">react</option>
                        </select>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="detail-agent-max-loop">Max Loop</Label>
                        <Input
                          id="detail-agent-max-loop"
                          type="number"
                          min={1}
                          max={20}
                          {...form.register("max_loop", { valueAsNumber: true })}
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="detail-agent-description">描述</Label>
                      <Textarea
                        id="detail-agent-description"
                        rows={3}
                        {...form.register("description")}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="detail-agent-prompt">System Prompt</Label>
                      <Textarea
                        id="detail-agent-prompt"
                        rows={6}
                        {...form.register("system_prompt")}
                      />
                    </div>
                    <div className="flex justify-end">
                      <Button type="submit" disabled={updateConfig.isPending}>
                        {updateConfig.isPending ? "保存中..." : "保存基础配置"}
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            ) : null}

            {value === "tools" ? (
              <Card>
                <CardHeader>
                  <CardTitle>{title}</CardTitle>
                  <CardDescription>{desc}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-slate-950">当前已启用</p>
                    {detail.data?.tools?.length ? (
                      detail.data.tools.map((tool) => (
                        <div
                          key={tool.id}
                          className="flex flex-col gap-4 rounded-2xl border border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between"
                        >
                          <div>
                            <p className="font-medium text-slate-950">{tool.tool_name}</p>
                            <p className="mt-1 text-sm text-slate-500">
                              enabled: {tool.enabled ? "true" : "false"}
                            </p>
                          </div>
                          <Button
                            variant="outline"
                            onClick={() => removeTool.mutate(tool.id)}
                            disabled={removeTool.isPending}
                          >
                            移除
                          </Button>
                        </div>
                      ))
                    ) : (
                      <EmptyState
                        title="当前没有启用内置工具"
                        description="可以从下方能力目录中把 calculator、datetime、rag_retrieval 等工具加入到当前助手。"
                      />
                    )}
                  </div>
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-slate-950">能力目录</p>
                    {builtinTools.data?.map((tool) => (
                      <div
                        key={tool.name}
                        className="flex flex-col gap-4 rounded-2xl border border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between"
                      >
                        <div>
                          <p className="font-medium text-slate-950">{tool.name}</p>
                          <p className="mt-1 text-sm text-slate-500">{tool.description}</p>
                        </div>
                        <Button
                          onClick={() =>
                            addTool.mutate({
                              tool_name: tool.name,
                              tool_config: {},
                              enabled: true,
                            })
                          }
                          disabled={linkedToolNames.has(tool.name) || addTool.isPending}
                        >
                          {linkedToolNames.has(tool.name) ? "已添加" : "加入助手"}
                        </Button>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ) : null}

            {value === "mcp" ? (
              <Card>
                <CardHeader>
                  <CardTitle>{title}</CardTitle>
                  <CardDescription>{desc}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-slate-950">当前关联的 MCP</p>
                    {detail.data?.mcp_servers?.length ? (
                      detail.data.mcp_servers.map((item) => (
                        <div
                          key={item.id}
                          className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4"
                        >
                          <div>
                            <p className="font-medium text-slate-950">{item.mcp_server_id}</p>
                            <p className="mt-1 text-sm text-slate-500">link id: {item.id}</p>
                          </div>
                          <Button
                            variant="outline"
                            onClick={() => unlinkMcp.mutate(item.id)}
                            disabled={unlinkMcp.isPending}
                          >
                            移除
                          </Button>
                        </div>
                      ))
                    ) : (
                      <EmptyState
                        title="当前没有绑定 MCP"
                        description="从系统配置里维护 MCP Server 后，可以在这里把它们绑定到当前助手。"
                      />
                    )}
                  </div>
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-slate-950">可关联的 MCP Server</p>
                    {mcpServers.data?.map((server) => (
                      <div
                        key={server.id}
                        className="flex flex-col gap-4 rounded-2xl border border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between"
                      >
                        <div>
                          <p className="font-medium text-slate-950">{server.name}</p>
                          <p className="mt-1 text-sm text-slate-500">
                            {server.transport} · {server.enabled ? "已启用" : "已禁用"}
                          </p>
                        </div>
                        <Button
                          onClick={() => linkMcp.mutate({ mcp_server_id: server.id })}
                          disabled={linkedMcpIds.has(server.id) || linkMcp.isPending}
                        >
                          {linkedMcpIds.has(server.id) ? "已关联" : "关联到助手"}
                        </Button>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ) : null}

            {value === "kb" ? (
              <Card>
                <CardHeader>
                  <CardTitle>{title}</CardTitle>
                  <CardDescription>{desc}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-slate-950">当前关联的知识库</p>
                    {detail.data?.kbs?.length ? (
                      detail.data.kbs.map((item) => (
                        <div
                          key={item.id}
                          className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4"
                        >
                          <div>
                            <p className="font-medium text-slate-950">{item.kb_id}</p>
                            <p className="mt-1 text-sm text-slate-500">link id: {item.id}</p>
                          </div>
                          <Button
                            variant="outline"
                            onClick={() => unlinkKb.mutate(item.id)}
                            disabled={unlinkKb.isPending}
                          >
                            移除
                          </Button>
                        </div>
                      ))
                    ) : (
                      <EmptyState
                        title="当前没有默认知识库"
                        description="将知识库关联到当前助手后，聊天时就能使用这些 KB 作为默认检索资源。"
                      />
                    )}
                  </div>
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-slate-950">可关联的知识库</p>
                    {knowledgeBases.data?.items.map((kb) => (
                      <div
                        key={kb.id}
                        className="flex flex-col gap-4 rounded-2xl border border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between"
                      >
                        <div>
                          <p className="font-medium text-slate-950">{kb.name}</p>
                          <p className="mt-1 text-sm text-slate-500">
                            top_k {kb.top_k} · {kb.is_active ? "已启用" : "未启用"}
                          </p>
                        </div>
                        <Button
                          onClick={() => linkKb.mutate({ kb_id: kb.id, kb_config: {} })}
                          disabled={linkedKbIds.has(kb.id) || linkKb.isPending}
                        >
                          {linkedKbIds.has(kb.id) ? "已关联" : "关联到助手"}
                        </Button>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ) : null}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
