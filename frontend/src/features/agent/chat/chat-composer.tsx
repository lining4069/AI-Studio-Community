import { SendHorizonal } from "lucide-react";
import type { RefObject } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type ChatComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isSending?: boolean;
  textareaRef?: RefObject<HTMLTextAreaElement | null>;
};

export function ChatComposer({
  value,
  onChange,
  onSend,
  isSending = false,
  textareaRef,
}: ChatComposerProps) {
  return (
    <div className="space-y-3">
      <Textarea
        ref={textareaRef}
        rows={5}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== "Enter" || event.shiftKey) {
            return;
          }

          event.preventDefault();

          if (!isSending && value.trim()) {
            onSend();
          }
        }}
        placeholder="继续向当前助手提问..."
      />
      <div className="flex items-center justify-between gap-3 text-xs text-slate-400">
        <p>当前阶段先走非流式正式版，后续再增强 SSE 实时输出。</p>
        <Button onClick={onSend} disabled={isSending || !value.trim()}>
          <SendHorizonal className="mr-2 size-4" />
          {isSending ? "发送中..." : "发送"}
        </Button>
      </div>
    </div>
  );
}
