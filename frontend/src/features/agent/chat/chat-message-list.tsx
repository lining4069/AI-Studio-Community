import { Bot, CircleEllipsis, UserRound } from "lucide-react";
import { useEffect, useRef } from "react";

import { EmptyState } from "@/components/shared/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";

import type { SessionMessage } from "@/features/agent/chat/types";
import { getMessageRoleLabel } from "@/features/agent/chat/utils";

type ChatMessageListProps = {
  messages: SessionMessage[];
  isSending?: boolean;
  pendingInput?: string;
  streamingAssistantContent?: string;
  errorMessage?: string | null;
  onPickSuggestion?: (value: string) => void;
};

const starterPrompts = [
  "先帮我总结当前助手的能力边界",
  "请列出当前会话可用的工具与知识库资源",
  "结合现有配置，给我一个适合继续追问的方向",
];

export function ChatMessageList({
  messages,
  isSending = false,
  pendingInput,
  streamingAssistantContent,
  errorMessage,
  onPickSuggestion,
}: ChatMessageListProps) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!messages.length && !pendingInput && !errorMessage) {
      return;
    }

    if (typeof endRef.current?.scrollIntoView === "function") {
      endRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [errorMessage, messages.length, pendingInput, isSending]);

  if (!messages.length && !pendingInput) {
    return (
      <div className="space-y-5">
        <EmptyState
          title="当前还没有历史消息"
          description="从这里开始和当前助手进行第一轮对话。发送问题后，你会看到正式消息流和执行步骤，而不是原始 JSON。"
        />
        <div className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-slate-950">推荐首问</p>
          <div className="mt-4 flex flex-wrap gap-3">
            {starterPrompts.map((prompt) => (
              <Button
                key={prompt}
                variant="outline"
                onClick={() => onPickSuggestion?.(prompt)}
                className="rounded-full"
              >
                {prompt}
              </Button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {messages.map((message, index) => {
        const isUser = message.role === "user";
        return (
          <div
            key={message.id ?? `${message.role ?? "message"}-${index}`}
            className={cn(
              "flex gap-4",
              isUser ? "justify-end" : "justify-start",
            )}
          >
            {!isUser ? (
              <div className="mt-1 flex size-10 shrink-0 items-center justify-center rounded-2xl bg-sky-100 text-sky-700">
                <Bot className="size-5" />
              </div>
            ) : null}
            <div
              className={cn(
                "max-w-3xl rounded-[1.75rem] border p-5 shadow-sm",
                isUser
                  ? "border-sky-200 bg-sky-600 text-white"
                  : "border-slate-200 bg-white text-slate-900",
              )}
            >
              <div className="flex flex-wrap items-center gap-3">
                <Badge
                  className={cn(
                    "border-transparent",
                    isUser
                      ? "bg-white/15 text-white hover:bg-white/15"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-100",
                  )}
                >
                  {getMessageRoleLabel(message.role)}
                </Badge>
                {message.created_at ? (
                  <span
                    className={cn(
                      "text-xs",
                      isUser ? "text-white/75" : "text-slate-400",
                    )}
                  >
                    {formatDate(message.created_at)}
                  </span>
                ) : null}
              </div>
              <p
                className={cn(
                  "mt-4 whitespace-pre-wrap text-sm leading-7",
                  isUser ? "text-white" : "text-slate-700",
                )}
              >
                {message.content || "当前消息内容为空。"}
              </p>
            </div>
            {isUser ? (
              <div className="mt-1 flex size-10 shrink-0 items-center justify-center rounded-2xl bg-slate-200 text-slate-700">
                <UserRound className="size-5" />
              </div>
            ) : null}
          </div>
        );
      })}

      {isSending && pendingInput ? (
        <div className="flex justify-end gap-4">
          <div className="max-w-3xl rounded-[1.75rem] border border-sky-200 bg-sky-600 p-5 text-white shadow-sm">
            <Badge className="border-transparent bg-white/15 text-white hover:bg-white/15">
              用户消息
            </Badge>
            <p className="mt-4 whitespace-pre-wrap text-sm leading-7">{pendingInput}</p>
          </div>
          <div className="mt-1 flex size-10 shrink-0 items-center justify-center rounded-2xl bg-slate-200 text-slate-700">
            <UserRound className="size-5" />
          </div>
        </div>
      ) : null}

      {streamingAssistantContent || isSending ? (
        <div className="flex gap-4">
          <div className="mt-1 flex size-10 shrink-0 items-center justify-center rounded-2xl bg-sky-100 text-sky-700">
            <Bot className="size-5" />
          </div>
          <div className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
            <Badge className="bg-slate-100 text-slate-700 hover:bg-slate-100">
              助手回答
            </Badge>
            {streamingAssistantContent ? (
              <div className="mt-4 space-y-3">
                <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
                  {streamingAssistantContent}
                </p>
                {isSending ? (
                  <div className="flex items-center gap-3 text-sm text-slate-500">
                    <CircleEllipsis className="size-4 animate-pulse" />
                    助手仍在继续生成中...
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="mt-4 flex items-center gap-3 text-sm text-slate-500">
                <CircleEllipsis className="size-4 animate-pulse" />
                正在发送，本次回复生成中...
              </div>
            )}
          </div>
        </div>
      ) : null}

      {errorMessage ? (
        <div className="rounded-[1.75rem] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700 shadow-sm">
          <p className="font-medium text-rose-900">本次执行失败，请重试</p>
          <p className="mt-2 whitespace-pre-wrap leading-6">{errorMessage}</p>
        </div>
      ) : null}

      <div ref={endRef} />
    </div>
  );
}
