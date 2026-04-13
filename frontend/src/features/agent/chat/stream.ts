export type AgentStreamEvent = {
  event: string;
  data: Record<string, unknown>;
};

export type ParsedAgentStreamBuffer = {
  events: AgentStreamEvent[];
  remainder: string;
};

function parseEventBlock(block: string): AgentStreamEvent | null {
  const lines = block.split("\n");
  let eventName = "";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
      continue;
    }

    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }

  if (!eventName || !dataLines.length) {
    return null;
  }

  try {
    return {
      event: eventName,
      data: JSON.parse(dataLines.join("\n")) as Record<string, unknown>,
    };
  } catch {
    return null;
  }
}

export function parseAgentStreamBuffer(buffer: string): ParsedAgentStreamBuffer {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const lines = normalized.split("\n");
  const events: AgentStreamEvent[] = [];
  const currentBlock: string[] = [];

  for (const line of lines) {
    if (line === "") {
      if (!currentBlock.length) {
        continue;
      }

      const parsed = parseEventBlock(currentBlock.join("\n"));
      if (parsed) {
        events.push(parsed);
      }
      currentBlock.length = 0;
      continue;
    }

    currentBlock.push(line);
  }

  return {
    events,
    remainder: currentBlock.join("\n"),
  };
}
