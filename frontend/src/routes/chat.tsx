import { useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  useAgentConfigDetail,
  useRunAgent,
  useSessionDetail,
  useSessionMessages,
  useSessionSteps,
} from "@/api/endpoints/agent";
import { EmptyState } from "@/components/shared/empty-state";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { deriveSessionTitle } from "@/features/agent/utils";
import { ChatComposer } from "@/features/agent/chat/chat-composer";
import { ChatHeader } from "@/features/agent/chat/chat-header";
import { ChatMessageList } from "@/features/agent/chat/chat-message-list";
import { ChatStepPanel } from "@/features/agent/chat/chat-step-panel";
import { type SessionMessage, type SessionStep } from "@/features/agent/chat/types";
import {
  normalizeMessage,
  normalizeStep,
} from "@/features/agent/chat/utils";
import { getErrorMessage } from "@/lib/data";

export function ChatRoute() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const [input, setInput] = useState("");
  const [pendingInput, setPendingInput] = useState("");
  const session = useSessionDetail(sessionId);
  const agentConfig = useAgentConfigDetail(session.data?.config_id);
  const messages = useSessionMessages(sessionId);
  const steps = useSessionSteps(sessionId);
  const runAgent = useRunAgent(sessionId);

  const normalizedMessages: SessionMessage[] = (messages.data ?? []).map(normalizeMessage);
  const normalizedSteps: SessionStep[] = (steps.data ?? []).map(normalizeStep);
  const effectiveTitle =
    session.data?.title ?? deriveSessionTitle(input || "默认会话");
  const errorMessage = runAgent.error
    ? getErrorMessage(runAgent.error, "本次执行失败，请重试")
    : null;

  const handleSend = async () => {
    if (!input.trim()) {
      return;
    }

    const submittedInput = input.trim();
    setPendingInput(submittedInput);
    setInput("");

    try {
      await runAgent.mutateAsync({
        input: submittedInput,
        stream: false,
        debug: false,
        mcp_server_ids: [],
      });
    } finally {
      setPendingInput("");
    }
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
      <div className="space-y-6">
        <ChatHeader
          title={effectiveTitle}
          updatedAt={session.data?.updated_at}
          sessionId={session.data?.id ?? sessionId}
          onBack={
            session.data?.config_id
              ? () => navigate(`/agents/${session.data.config_id}`)
              : undefined
          }
        />
        <Card className="min-h-[420px]">
          <CardContent className="space-y-4">
            <ChatMessageList
              messages={normalizedMessages}
              isSending={runAgent.isPending}
              pendingInput={runAgent.isPending ? pendingInput : undefined}
              errorMessage={errorMessage}
              onPickSuggestion={(value) => {
                setInput(value);
                composerRef.current?.focus();
              }}
            />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <ChatComposer
              value={input}
              onChange={setInput}
              onSend={handleSend}
              isSending={runAgent.isPending}
              textareaRef={composerRef}
            />
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6">
        {sessionId ? (
          <ChatStepPanel
            steps={normalizedSteps}
            sessionId={session.data?.id ?? sessionId}
            title={effectiveTitle}
            agentName={agentConfig.data?.name}
            agentDescription={agentConfig.data?.description ?? undefined}
            createdAt={session.data?.created_at}
            updatedAt={session.data?.updated_at}
          />
        ) : (
          <EmptyState
            title="当前缺少会话信息"
            description="请先从助手详情页创建或进入一个会话，再继续使用聊天工作区。"
          />
        )}
      </div>
    </div>
  );
}
