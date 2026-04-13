import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChatStepPanel } from "@/features/agent/chat/chat-step-panel";

describe("ChatStepPanel", () => {
  it("renders readable step type labels and guidance for think, tool, and result steps", () => {
    render(
      <ChatStepPanel
        title="调研 Agent 工作流"
        steps={[
          {
            id: "step-1",
            type: "think",
            name: "意图理解",
            status: "success",
            output: "识别到用户想要查看会话能力边界",
            created_at: "2026-04-13T12:10:05Z",
          },
          {
            id: "step-2",
            type: "tool",
            name: "rag_retrieval",
            status: "success",
            output: "检索到 3 个关联片段",
            created_at: "2026-04-13T12:10:06Z",
          },
          {
            id: "step-3",
            type: "result",
            name: "最终整理",
            status: "success",
            output: "已经整理成结构化回答",
            created_at: "2026-04-13T12:10:08Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("思考")).toBeInTheDocument();
    expect(screen.getByText("工具调用")).toBeInTheDocument();
    expect(screen.getByText("执行结果")).toBeInTheDocument();
    expect(screen.getByText("整理助手当前的思路与判断。")).toBeInTheDocument();
    expect(screen.getByText("记录本次实际调用的工具与外部能力。")).toBeInTheDocument();
    expect(screen.getByText("汇总本轮执行后沉淀出的输出或结论。")).toBeInTheDocument();
  });

  it("highlights the latest step and failed step for quick scanning", () => {
    render(
      <ChatStepPanel
        title="调研 Agent 工作流"
        steps={[
          {
            id: "step-1",
            type: "think",
            name: "意图理解",
            status: "success",
            output: "识别到用户问题",
            created_at: "2026-04-13T12:10:05Z",
          },
          {
            id: "step-2",
            type: "tool",
            name: "rag_retrieval",
            status: "failed",
            error: "检索服务暂时不可用",
            created_at: "2026-04-13T12:10:06Z",
          },
          {
            id: "step-3",
            type: "result",
            name: "最终整理",
            status: "running",
            output: "正在组织最终回答",
            created_at: "2026-04-13T12:10:08Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("最近一步")).toBeInTheDocument();
    expect(screen.getByText("执行异常")).toBeInTheDocument();
    expect(screen.getByText("检索服务暂时不可用")).toBeInTheDocument();
  });
});
