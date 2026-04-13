import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import {
  runAgentStream,
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
import type { AgentStreamEvent } from "@/features/agent/chat/stream";
import {
  normalizeMessage,
  normalizeStep,
} from "@/features/agent/chat/utils";
import { getErrorMessage } from "@/lib/data";

function mergeStreamStep(
  currentSteps: SessionStep[],
  event: AgentStreamEvent,
): SessionStep[] {
  const data = event.data;
  const stepId =
    typeof data.step_id === "string"
      ? data.step_id
      : undefined;
  const stepIndex =
    typeof data.step_index === "number"
      ? data.step_index
      : undefined;

  if (
    !stepId &&
    stepIndex == null &&
    !["step_start", "step_end", "tool_call", "tool_result", "content", "error"].includes(
      event.event,
    )
  ) {
    return currentSteps;
  }

  const nextStep: SessionStep = {
    id: stepId,
    step_index: stepIndex,
    type: typeof data.type === "string" ? data.type : undefined,
    name: typeof data.name === "string" ? data.name : undefined,
    status: typeof data.status === "string" ? data.status : undefined,
    output: data.output,
    error: typeof data.error === "string" ? data.error : null,
    created_at: typeof data.created_at === "string" ? data.created_at : undefined,
  };

  const index = currentSteps.findIndex((step) => {
    if (stepId && step.id === stepId) {
      return true;
    }
    return stepIndex != null && step.step_index === stepIndex;
  });

  if (index === -1) {
    return [
      ...currentSteps,
      nextStep,
    ].sort(
      (left, right) =>
        (left.step_index ?? Number.MAX_SAFE_INTEGER) -
        (right.step_index ?? Number.MAX_SAFE_INTEGER),
    );
  }

  const updated = [...currentSteps];
  updated[index] = {
    ...updated[index],
    ...Object.fromEntries(
      Object.entries(nextStep).filter(([, value]) => value !== undefined),
    ),
  };
  return updated;
}

export function ChatRoute() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const [input, setInput] = useState("");
  const [pendingInput, setPendingInput] = useState("");
  const [streamSteps, setStreamSteps] = useState<SessionStep[] | null>(null);
  const [streamAssistantContent, setStreamAssistantContent] = useState("");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const session = useSessionDetail(sessionId);
  const agentConfig = useAgentConfigDetail(session.data?.config_id);
  const messages = useSessionMessages(sessionId);
  const steps = useSessionSteps(sessionId);
  const runAgent = useRunAgent(sessionId);

  const normalizedMessages: SessionMessage[] = (messages.data ?? []).map(normalizeMessage);
  const normalizedSteps: SessionStep[] = (steps.data ?? []).map(normalizeStep);
  const effectiveSteps = streamSteps ?? normalizedSteps;
  const effectiveTitle =
    session.data?.title ?? deriveSessionTitle(input || "默认会话");
  const errorMessage = streamError ?? (runAgent.error
    ? getErrorMessage(runAgent.error, "本次执行失败，请重试")
    : null);

  useEffect(() => {
    if (!streamAssistantContent) {
      return;
    }

    const latestAssistantMessage = [...normalizedMessages]
      .reverse()
      .find((message) => message.role === "assistant" && message.content);

    if (
      latestAssistantMessage?.content &&
      latestAssistantMessage.content.includes(streamAssistantContent)
    ) {
      setStreamAssistantContent("");
    }
  }, [normalizedMessages, streamAssistantContent]);

  const handleSend = async () => {
    if (!input.trim() || !sessionId) {
      return;
    }

    const submittedInput = input.trim();
    setPendingInput(submittedInput);
    setInput("");
    setStreamError(null);
    setStreamSteps(normalizedSteps);
    setStreamAssistantContent("");
    setIsStreaming(true);
    let receivedStreamEvent = false;

    try {
      await runAgentStream(sessionId, {
        payload: {
          input: submittedInput,
          stream: true,
          debug: false,
          mcp_server_ids: [],
        },
        onEvent: (event) => {
          receivedStreamEvent = true;

          if (event.event === "error") {
            setStreamError(
              typeof event.data.message === "string"
                ? event.data.message
                : "本次流式执行失败，请重试",
            );
          }

          if (event.event === "content") {
            const content =
              typeof event.data.content === "string" ? event.data.content : "";
            if (content) {
              setStreamAssistantContent((current) => current + content);
            }
          }

          setStreamSteps((current) =>
            mergeStreamStep(current ?? normalizedSteps, event),
          );
        },
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["agent", "sessions"] }),
        queryClient.invalidateQueries({ queryKey: ["agent", "sessions", sessionId] }),
        queryClient.invalidateQueries({
          queryKey: ["agent", "sessions", sessionId, "messages"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["agent", "sessions", sessionId, "steps"],
        }),
      ]);
    } catch (error) {
      if (!receivedStreamEvent) {
        await runAgent.mutateAsync({
          input: submittedInput,
          stream: false,
          debug: false,
          mcp_server_ids: [],
        });
      } else {
        setStreamError(
          getErrorMessage(error, "本次流式执行失败，请重试"),
        );
      }
    } finally {
      setIsStreaming(false);
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
              isSending={isStreaming || runAgent.isPending}
              pendingInput={isStreaming || runAgent.isPending ? pendingInput : undefined}
              streamingAssistantContent={streamAssistantContent}
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
              isSending={isStreaming || runAgent.isPending}
              textareaRef={composerRef}
            />
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6">
        {sessionId ? (
          <ChatStepPanel
            steps={effectiveSteps}
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
