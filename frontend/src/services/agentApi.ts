export type AgentEvent =
  | { type: "run_started"; run_id: string; thread_id: string }
  | { type: "message_delta"; run_id?: string; thread_id?: string; delta: string }
  | { type: "activity"; run_id?: string; thread_id?: string; activity: string }
  | { type: "run_finished"; run_id?: string; thread_id?: string; finish_reason?: string }
  | { type: "error"; run_id?: string; thread_id?: string; message: string };

export type ChatHistoryItem = {
  role: "user" | "assistant";
  content: string;
};

type StreamRunArgs = {
  threadId: string;
  message: string;
  history?: ChatHistoryItem[];
  signal?: AbortSignal;
  onEvent: (event: AgentEvent) => void;
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

export async function createSession(signal?: AbortSignal): Promise<string> {
  const response = await fetch(`${API_BASE}/sessions`, {
    method: "POST",
    signal
  });
  if (!response.ok) {
    throw new Error("Unable to create a session.");
  }
  const payload = (await response.json()) as { thread_id: string };
  return payload.thread_id;
}

export async function streamRun({ threadId, message, history = [], signal, onEvent }: StreamRunArgs): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${threadId}/runs/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ message, history }),
    signal
  });

  if (!response.ok || !response.body) {
    throw new Error("Unable to stream the agent run.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const event = parseEvent(line);
      if (event) {
        onEvent(event);
      }
    }
  }

  const finalLine = buffer.trim();
  if (finalLine) {
    const event = parseEvent(finalLine);
    if (event) {
      onEvent(event);
    }
  }
}

function parseEvent(line: string): AgentEvent | null {
  const trimmed = line.trim();
  if (!trimmed) {
    return null;
  }
  return JSON.parse(trimmed) as AgentEvent;
}
