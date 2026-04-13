import { describe, expect, it } from "vitest";

import { parseAgentStreamBuffer } from "@/features/agent/chat/stream";

describe("parseAgentStreamBuffer", () => {
  it("parses complete SSE events from a buffer", () => {
    const result = parseAgentStreamBuffer(
      [
        'event: step_start',
        'data: {"step_index":0,"name":"意图理解"}',
        "",
        'event: run_end',
        'data: {"output":"完成"}',
        "",
      ].join("\n"),
    );

    expect(result.remainder).toBe("");
    expect(result.events).toEqual([
      {
        event: "step_start",
        data: { step_index: 0, name: "意图理解" },
      },
      {
        event: "run_end",
        data: { output: "完成" },
      },
    ]);
  });

  it("keeps partial chunks in remainder until the next delimiter arrives", () => {
    const first = parseAgentStreamBuffer(
      ['event: content', 'data: {"delta":"你好"}'].join("\n"),
    );

    expect(first.events).toEqual([]);
    expect(first.remainder).toContain("event: content");

    const second = parseAgentStreamBuffer(
      `${first.remainder}\n\nevent: error\ndata: {"message":"失败"}\n\n`,
    );

    expect(second.remainder).toBe("");
    expect(second.events).toEqual([
      {
        event: "content",
        data: { delta: "你好" },
      },
      {
        event: "error",
        data: { message: "失败" },
      },
    ]);
  });

  it("ignores malformed event payloads without breaking later events", () => {
    const result = parseAgentStreamBuffer(
      [
        'event: step_end',
        'data: {"broken": }',
        "",
        'event: run_end',
        'data: {"output":"ok"}',
        "",
      ].join("\n"),
    );

    expect(result.events).toEqual([
      {
        event: "run_end",
        data: { output: "ok" },
      },
    ]);
  });
});
