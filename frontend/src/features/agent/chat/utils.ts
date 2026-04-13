import { clampText } from "@/lib/utils";

import type { SessionMessage, SessionStep } from "@/features/agent/chat/types";

export function normalizeMessage(input: unknown): SessionMessage {
  if (!input || typeof input !== "object") {
    return {};
  }

  const message = input as Record<string, unknown>;
  return {
    id: typeof message.id === "string" ? message.id : undefined,
    role: typeof message.role === "string" ? message.role : undefined,
    content: typeof message.content === "string" ? message.content : "",
    created_at:
      typeof message.created_at === "string" ? message.created_at : undefined,
  };
}

export function normalizeStep(input: unknown): SessionStep {
  if (!input || typeof input !== "object") {
    return {};
  }

  const step = input as Record<string, unknown>;
  return {
    id: typeof step.id === "string" ? step.id : undefined,
    step_index:
      typeof step.step_index === "number" ? step.step_index : undefined,
    type: typeof step.type === "string" ? step.type : undefined,
    name: typeof step.name === "string" ? step.name : undefined,
    status: typeof step.status === "string" ? step.status : undefined,
    output: step.output,
    error: typeof step.error === "string" ? step.error : null,
    created_at: typeof step.created_at === "string" ? step.created_at : undefined,
  };
}

export function getMessageRoleLabel(role?: string) {
  switch (role) {
    case "user":
      return "用户消息";
    case "assistant":
      return "助手回答";
    default:
      return "系统消息";
  }
}

export function getStepStatusLabel(status?: string) {
  switch (status) {
    case "success":
      return "已完成";
    case "failed":
      return "失败";
    case "running":
      return "执行中";
    default:
      return "待处理";
  }
}

export function stringifyStepOutput(output: unknown) {
  if (typeof output === "string") {
    return clampText(output, 96);
  }

  if (output == null) {
    return "当前步骤没有返回结果。";
  }

  try {
    return clampText(JSON.stringify(output, null, 2), 96);
  } catch {
    return "当前步骤返回了复杂结构。";
  }
}
