import { SendHorizonal } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";

import {
  useRunAgent,
  useSessionDetail,
  useSessionMessages,
  useSessionSteps,
} from "@/api/endpoints/agent";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState } from "@/components/shared/empty-state";
import { SectionHeading } from "@/components/shared/section-heading";
import { deriveSessionTitle } from "@/features/agent/utils";
import { formatDate } from "@/lib/utils";

export function ChatRoute() {
  const { sessionId } = useParams();
  const [input, setInput] = useState("");
  const [latestResult, setLatestResult] = useState<unknown>(null);
  const session = useSessionDetail(sessionId);
  const messages = useSessionMessages(sessionId);
  const steps = useSessionSteps(sessionId);
  const runAgent = useRunAgent(sessionId);

  const handleSend = async () => {
    if (!input.trim()) {
      return;
    }

    const result = await runAgent.mutateAsync({
      input,
      stream: false,
      debug: false,
      mcp_server_ids: [],
    });
    setLatestResult(result);
    setInput("");
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
      <div className="space-y-6">
        <SectionHeading
          eyebrow="Session"
          title={session.data?.title ?? "对话工作区"}
          description="聊天页围绕 Session 展开，消息发送到 `/v1/agent/sessions/{session_id}/runs`。当前默认走非流式运行，先把浏览器工作流跑顺。"
        />
        <Card className="min-h-[420px]">
          <CardHeader>
            <CardTitle>消息流</CardTitle>
            <CardDescription>这里会渲染消息历史、步骤和调试信息。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {messages.data?.length ? (
              messages.data.map((message, index) => (
                <div key={index} className="rounded-2xl border border-slate-200 p-4">
                  <pre className="whitespace-pre-wrap text-sm leading-6 text-slate-600">
                    {JSON.stringify(message, null, 2)}
                  </pre>
                </div>
              ))
            ) : latestResult ? (
              <div className="rounded-2xl border border-sky-200 bg-sky-50/60 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">
                  最新结果
                </p>
                <pre className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                  {JSON.stringify(latestResult, null, 2)}
                </pre>
              </div>
            ) : (
              <EmptyState
                title="当前还没有消息"
                description="Session 创建并绑定 AgentConfig 后，先发送一条消息，这里就会展示后端返回的消息流和运行结果。"
              />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="space-y-3">
              <Textarea
                rows={5}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="请输入你的问题，例如：使用网络搜索工具获取最新的华为手机型号"
              />
              <div className="flex justify-end">
                <Button onClick={handleSend} disabled={runAgent.isPending}>
                  <SendHorizonal className="mr-2 size-4" />
                  {runAgent.isPending ? "发送中..." : "发送"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>当前助手</CardTitle>
            <CardDescription>展示当前 Session 绑定的 AgentConfig 摘要。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-slate-500">
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="font-medium text-slate-950">Session ID</p>
              <p className="mt-2 break-all">{session.data?.id ?? sessionId}</p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="font-medium text-slate-950">会话标题</p>
              <p className="mt-2">
                {session.data?.title || deriveSessionTitle(input || "默认会话")}
              </p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="font-medium text-slate-950">创建时间</p>
              <p className="mt-2">
                {session.data?.created_at ? formatDate(session.data.created_at) : "等待加载"}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>运行面板</CardTitle>
            <CardDescription>用于展示 run_id、步骤、resume/stop 等调试入口。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-slate-500">
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="font-medium text-slate-950">步骤数量</p>
              <p className="mt-2">{steps.data?.length ?? 0}</p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="font-medium text-slate-950">运行模式</p>
              <p className="mt-2">当前页面默认使用非流式 run，后续再增强 SSE 可视化。</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
