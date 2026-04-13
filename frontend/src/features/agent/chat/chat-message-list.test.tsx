import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { ChatMessageList } from "@/features/agent/chat/chat-message-list";

const scrollIntoViewMock = vi.fn();
const onPickSuggestion = vi.fn();

describe("ChatMessageList", () => {
  beforeEach(() => {
    scrollIntoViewMock.mockReset();
    onPickSuggestion.mockReset();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoViewMock,
    });
  });

  test("renders starter suggestions when there is no history", async () => {
    const user = userEvent.setup();

    render(
      <ChatMessageList
        messages={[]}
        onPickSuggestion={onPickSuggestion}
      />,
    );

    expect(screen.getByText("当前还没有历史消息")).toBeInTheDocument();
    expect(screen.getByText("推荐首问")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "先帮我总结当前助手的能力边界" }));
    expect(onPickSuggestion).toHaveBeenCalledWith("先帮我总结当前助手的能力边界");
  });

  test("scrolls to the latest content when messages are present", () => {
    render(
      <ChatMessageList
        messages={[
          {
            id: "msg-1",
            role: "assistant",
            content: "这里是最新的回复内容",
            created_at: "2026-04-13T18:30:00Z",
          },
        ]}
      />,
    );

    expect(scrollIntoViewMock).toHaveBeenCalled();
  });
});
