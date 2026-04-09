import { Bot, MessageSquarePlus, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useAgentConfigs, useCreateSession } from "@/api/endpoints/agent";
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
import { CreateAgentForm } from "@/features/agent/create-agent-form";
import { formatDate } from "@/lib/utils";

export function AgentsRoute() {
  const [open, setOpen] = useState(false);
  const agentConfigs = useAgentConfigs();
  const createSession = useCreateSession();

  const handleQuickChat = async (configId: string) => {
    const session = await createSession.mutateAsync({
      config_id: configId,
      title: "默认会话",
    });

    window.location.hash = `#/chat/${session.id}`;
  };

  return (
    <div className="space-y-8">
      <SectionHeading
        eyebrow="Agent"
        title="助手"
        description="助手列表页以 AgentConfig 为中心，展示配置好的工具、MCP、KB 与聊天入口。"
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 size-4" />
                新建助手
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>创建助手</DialogTitle>
                <DialogDescription>
                  助手列表页以 AgentConfig 为中心，基础配置创建后可在详情页继续绑定工具、MCP 和知识库。
                </DialogDescription>
              </DialogHeader>
              <CreateAgentForm onSuccess={() => setOpen(false)} />
            </DialogContent>
          </Dialog>
        }
      />

      {agentConfigs.data?.length ? (
        <div className="grid gap-5 xl:grid-cols-3">
          {agentConfigs.data.map((agent) => (
            <Card
              key={agent.id}
              className="flex h-full flex-col transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-md"
            >
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex size-12 items-center justify-center rounded-2xl bg-sky-50 text-sky-600">
                    <Bot className="size-6" />
                  </div>
                  <p className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                    {agent.agent_type}
                  </p>
                </div>
                <CardTitle className="mt-4">{agent.name}</CardTitle>
                <CardDescription>
                  {agent.description || "这个助手还没有填写描述。"}
                </CardDescription>
              </CardHeader>
              <CardContent className="mt-auto space-y-4 text-sm text-slate-500">
                <div className="space-y-1">
                  <p>Max Loop：{agent.max_loop}</p>
                  <p>更新时间：{formatDate(agent.updated_at)}</p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link to={`/agents/${agent.id}`}>
                    <Button variant="outline">查看详情</Button>
                  </Link>
                  <Button
                    onClick={() => handleQuickChat(agent.id)}
                    disabled={createSession.isPending}
                  >
                    <MessageSquarePlus className="mr-2 size-4" />
                    新建对话
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          title="还没有助手"
          description="先创建一个 AgentConfig，随后在详情页继续绑定工具、MCP 和知识库。"
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus className="mr-2 size-4" />
              现在创建
            </Button>
          }
        />
      )}
    </div>
  );
}
