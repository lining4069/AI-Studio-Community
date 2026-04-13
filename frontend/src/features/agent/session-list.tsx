import { History, LoaderCircle, MessageSquareText, RefreshCw } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { AgentSessionResponse } from "@/api/types";
import { clampText, formatDate } from "@/lib/utils";

type SessionListProps = {
  sessions: AgentSessionResponse[];
  isLoading?: boolean;
  isRefreshing?: boolean;
  onRefresh: () => void;
  onOpenSession: (sessionId: string) => void;
  onCreateSession: () => void;
  isCreatingSession?: boolean;
};

export function SessionList({
  sessions,
  isLoading = false,
  isRefreshing = false,
  onRefresh,
  onOpenSession,
  onCreateSession,
  isCreatingSession = false,
}: SessionListProps) {
  return (
    <Card className="overflow-hidden border-slate-200/80 shadow-sm">
      <CardHeader className="border-b border-slate-200/70 bg-[linear-gradient(135deg,#f8fafc_0%,#eef6ff_52%,#effcf7_100%)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
              <History className="size-3.5 text-sky-600" />
              Session Workspace
            </div>
            <div className="space-y-1">
              <CardTitle className="text-xl text-slate-950">会话工作区</CardTitle>
              <CardDescription className="max-w-3xl text-sm text-slate-600">
                在当前助手上下文里查看历史对话、继续已有会话，或直接发起新的工作流。
              </CardDescription>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              onClick={onRefresh}
              disabled={isRefreshing || isLoading}
            >
              <RefreshCw className="mr-2 size-4" />
              刷新会话列表
            </Button>
            <Button onClick={onCreateSession} disabled={isCreatingSession}>
              <MessageSquareText className="mr-2 size-4" />
              {isCreatingSession ? "创建中..." : "新建对话"}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 p-6">
        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200/80 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
          <span className="font-medium text-slate-900">
            共 {sessions.length} 个历史会话
          </span>
          <span>继续对话会沿用当前助手配置与关联能力。</span>
        </div>

        {isLoading ? (
          <div className="flex min-h-40 items-center justify-center rounded-3xl border border-dashed border-slate-200 bg-slate-50/70 text-sm text-slate-500">
            <LoaderCircle className="mr-2 size-4 animate-spin" />
            会话列表加载中...
          </div>
        ) : sessions.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {sessions.map((session) => (
              <div
                key={session.id}
                className="rounded-3xl border border-slate-200/80 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <p className="text-base font-semibold text-slate-950">
                      {clampText(session.title || "默认会话", 32)}
                    </p>
                    <p className="text-sm leading-6 text-slate-600">
                      {clampText(
                        session.latest_message_preview || "当前会话还没有沉淀消息摘要。",
                        88,
                      )}
                    </p>
                    <div className="space-y-1 text-sm text-slate-500">
                      <p>最近更新：{formatDate(session.updated_at)}</p>
                      <p>创建时间：{formatDate(session.created_at)}</p>
                    </div>
                  </div>
                  <p className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                    {session.summary ? "已总结" : "进行中"}
                  </p>
                </div>
                <div className="mt-5 flex items-center justify-between gap-3">
                  <p className="text-xs text-slate-400">Session ID：{session.id}</p>
                  <Button onClick={() => onOpenSession(session.id)}>继续对话</Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="当前助手还没有会话"
            description="先创建第一条对话，后续就能围绕这个助手持续积累历史会话与调试记录。"
            action={
              <Button onClick={onCreateSession} disabled={isCreatingSession}>
                <MessageSquareText className="mr-2 size-4" />
                立即开始
              </Button>
            }
          />
        )}
      </CardContent>
    </Card>
  );
}
