import { Bot, Hammer, ListChecks, Sparkles } from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";

import type { SessionStep } from "@/features/agent/chat/types";
import {
  getStepStatusLabel,
  stringifyStepOutput,
} from "@/features/agent/chat/utils";

type ChatStepPanelProps = {
  steps: SessionStep[];
  sessionId?: string;
  title: string;
  createdAt?: string;
  updatedAt?: string;
};

function getStepIcon(type?: string) {
  switch (type) {
    case "tool":
      return Hammer;
    case "think":
      return Sparkles;
    default:
      return Bot;
  }
}

export function ChatStepPanel({
  steps,
  sessionId,
  title,
  createdAt,
  updatedAt,
}: ChatStepPanelProps) {
  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
          <ListChecks className="size-4 text-sky-600" />
          Session Summary
        </div>
        <div className="mt-5 space-y-4 text-sm text-slate-500">
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="font-medium text-slate-950">会话标题</p>
            <p className="mt-2 text-slate-700">{title}</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="font-medium text-slate-950">Session ID</p>
            <p className="mt-2 break-all">{sessionId ?? "等待加载"}</p>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1">
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="font-medium text-slate-950">创建时间</p>
              <p className="mt-2">{createdAt ? formatDate(createdAt) : "等待加载"}</p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="font-medium text-slate-950">最近更新</p>
              <p className="mt-2">{updatedAt ? formatDate(updatedAt) : "等待加载"}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-slate-950">本次执行步骤</h3>
            <p className="mt-1 text-sm text-slate-500">
              用更可读的方式查看本会话的推理、工具调用和执行反馈。
            </p>
          </div>
          <Badge className="bg-slate-100 text-slate-700 hover:bg-slate-100">
            共 {steps.length} 步
          </Badge>
        </div>

        {steps.length ? (
          <div className="mt-6 space-y-4">
            {steps.map((step, index) => {
              const Icon = getStepIcon(step.type);
              return (
                <div
                  key={step.id ?? `${step.name ?? "step"}-${index}`}
                  className="rounded-[1.6rem] border border-slate-200 p-4"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex gap-3">
                      <div className="mt-1 flex size-10 shrink-0 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
                        <Icon className="size-5" />
                      </div>
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-medium text-slate-950">
                            {step.name || `步骤 ${step.step_index ?? index + 1}`}
                          </p>
                          <Badge className="bg-sky-50 text-sky-700 hover:bg-sky-50">
                            {step.type ?? "step"}
                          </Badge>
                          <Badge className="bg-slate-100 text-slate-700 hover:bg-slate-100">
                            {getStepStatusLabel(step.status)}
                          </Badge>
                        </div>
                        <p className="text-sm leading-6 text-slate-600">
                          {step.error || stringifyStepOutput(step.output)}
                        </p>
                      </div>
                    </div>
                    <p className="text-xs text-slate-400">
                      {step.created_at ? formatDate(step.created_at) : `Step ${index + 1}`}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-6">
            <EmptyState
              title="当前还没有执行步骤"
              description="先发送一条消息，助手完成推理与工具调用后，这里就会沉淀可回看的执行过程。"
            />
          </div>
        )}
      </div>
    </div>
  );
}
