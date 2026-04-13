import { ArrowLeft, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";

type ChatHeaderProps = {
  title: string;
  updatedAt?: string | null;
  sessionId?: string;
  onBack?: () => void;
};

export function ChatHeader({
  title,
  updatedAt,
  sessionId,
  onBack,
}: ChatHeaderProps) {
  return (
    <div className="rounded-[2rem] border border-slate-200/80 bg-[linear-gradient(145deg,#0f172a_0%,#115e59_48%,#f3fbff_100%)] p-6 text-white shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <Badge className="border-white/15 bg-white/10 text-white hover:bg-white/10">
            <Sparkles className="mr-2 size-3.5" />
            Agent Session
          </Badge>
          {updatedAt ? (
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-white/70">
              最近更新 {formatDate(updatedAt)}
            </span>
          ) : null}
        </div>
        {onBack ? (
          <Button
            variant="outline"
            onClick={onBack}
            className="border-white/15 bg-white/10 text-white hover:bg-white/15 hover:text-white"
          >
            <ArrowLeft className="mr-2 size-4" />
            返回助手详情
          </Button>
        ) : null}
      </div>
      <div className="mt-4 space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        <p className="max-w-3xl text-sm leading-6 text-white/80">
          围绕当前会话持续提问、追踪执行步骤，并在同一个工作区里理解助手如何完成推理与工具调用。
        </p>
        {sessionId ? (
          <p className="text-xs tracking-[0.14em] text-white/60">
            SESSION ID · {sessionId}
          </p>
        ) : null}
      </div>
    </div>
  );
}
