import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatComposer } from "@/features/agent/chat/chat-composer";

describe("ChatComposer", () => {
  it("sends on Enter and keeps Shift+Enter for multiline input", () => {
    const onChange = vi.fn();
    const onSend = vi.fn();

    render(
      <ChatComposer
        value="请帮我总结一下当前助手能力"
        onChange={onChange}
        onSend={onSend}
      />,
    );

    const textarea = screen.getByPlaceholderText("继续向当前助手提问...");

    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(onSend).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(onSend).toHaveBeenCalledTimes(1);
  });
});
