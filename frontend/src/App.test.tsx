import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { AgentActivity } from "./components/AgentActivity";
import { MarkdownResponse } from "./components/MarkdownResponse";
import i18n from "./i18n";

const CHAT_STORAGE_KEY = "bit-professor-agent:conversation:v1";

describe("BIT Professor Agent frontend", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    i18n.changeLanguage("en");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("renders the opening UI without fake conversation messages or a native form", () => {
    const { container } = render(<App />);

    expect(screen.getByText("Knowing the Professors")).toBeInTheDocument();
    expect(screen.getByText("Find BIT professors by research topic, department, or name.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Contribute on GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/khajiev13/bit-international-students"
    );
    expect(screen.queryByText(/workspace/i)).not.toBeInTheDocument();
    expect(screen.getByText("Try asking")).toBeInTheDocument();
    expect(container.querySelector(".quick-start.primary")).not.toBeInTheDocument();
    expect(container.querySelector(".quick-start b")).not.toBeInTheDocument();
    expect(screen.getByText(/22 departments and 753 professor profiles/)).toBeInTheDocument();
    expect(screen.queryByText("Compare professors")).not.toBeInTheDocument();
    expect(screen.queryByText(/compare research directions/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Agent response")).not.toBeInTheDocument();
    expect(screen.queryByText("Markdown")).not.toBeInTheDocument();
    expect(screen.queryByText("Agent activity")).not.toBeInTheDocument();
    expect(container.querySelector("form")).not.toBeInTheDocument();
  });

  it("switches between English and Chinese labels", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "中文" }));

    expect(screen.getByText("可以这样问")).toBeInTheDocument();
    expect(screen.getByText("认识教授")).toBeInTheDocument();
    expect(screen.getByText("按研究主题、院系或姓名查找北京理工大学教授。")).toBeInTheDocument();
    expect(screen.queryByText("比较教授")).not.toBeInTheDocument();
  });

  it("fills the composer from quick-start prompts", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /Research direction/ }));

    expect(screen.getByPlaceholderText("Ask about a topic or a BIT professor...")).toHaveValue(
      "Which BIT professors across departments work on machine learning and artificial intelligence?"
    );
  });

  it("sanitizes markdown rendering", () => {
    const { container } = render(
      <MarkdownResponse
        markdown={"# Safe\n\n<script>alert('bad')</script>\n\n| A | B |\n| - | - |\n| 1 | 2 |"}
      />
    );

    expect(screen.getByRole("heading", { name: "Safe" })).toBeInTheDocument();
    expect(container.querySelector("script")).not.toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("renders activity when events arrive", () => {
    render(<AgentActivity title="Agent activity" items={["Searching professor profiles"]} />);

    expect(screen.getByText("Agent activity")).toBeInTheDocument();
    expect(screen.getByText("Searched professor profiles")).toBeInTheDocument();
  });

  it("restores a stored transcript from localStorage", () => {
    localStorage.setItem(
      CHAT_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        conversationId: "conversation-test",
        updatedAt: "2026-04-26T00:00:00.000Z",
        messages: [
          {
            id: "user-1",
            role: "user",
            content: "Who works on machine learning?",
            createdAt: "2026-04-26T00:00:00.000Z",
            status: "complete"
          },
          {
            id: "assistant-1",
            role: "assistant",
            content: "Li Xin works on machine learning.",
            createdAt: "2026-04-26T00:00:01.000Z",
            status: "complete"
          }
        ]
      })
    );

    const { container } = render(<App />);

    expect(screen.getByText("Who works on machine learning?")).toBeInTheDocument();
    expect(screen.getByText("Li Xin works on machine learning.")).toBeInTheDocument();
    expect(screen.getByText("Try asking")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Research direction/ })).toBeInTheDocument();
    expect(container.querySelector(".quick-panel.is-conversation-active")).toBeInTheDocument();
  });

  it("does not show agent activity for completed assistant messages", () => {
    localStorage.setItem(
      CHAT_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        conversationId: "conversation-test",
        updatedAt: "2026-04-26T00:00:00.000Z",
        messages: [
          {
            id: "assistant-1",
            role: "assistant",
            content: "Final answer.",
            createdAt: "2026-04-26T00:00:01.000Z",
            status: "complete",
            activity: ["Searching professor profiles"]
          }
        ]
      })
    );

    render(<App />);

    expect(screen.getByText("Final answer.")).toBeInTheDocument();
    expect(screen.queryByText("Agent activity")).not.toBeInTheDocument();
  });

  it("appends streamed user and assistant messages and persists the final response", async () => {
    const user = userEvent.setup();
    const fetchMock = mockStreamingFetch([
      { type: "run_started", run_id: "run-1", thread_id: "conversation-test" },
      { type: "message_delta", delta: "Li Xin " },
      { type: "message_delta", delta: "works on machine learning." },
      { type: "run_finished", finish_reason: "completed" }
    ]);

    render(<App />);
    await user.type(screen.getByPlaceholderText("Ask about a topic or a BIT professor..."), "Who works on ML?");
    await user.click(screen.getByRole("button", { name: "ASK" }));

    expect(await screen.findByText("Who works on ML?")).toBeInTheDocument();
    expect(await screen.findByText("Li Xin works on machine learning.")).toBeInTheDocument();

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(request.body as string)).toEqual({ message: "Who works on ML?", history: [] });

    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || "{}");
      expect(stored.messages).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ role: "user", content: "Who works on ML?" }),
          expect.objectContaining({ role: "assistant", content: "Li Xin works on machine learning." })
        ])
      );
    });
  });

  it("shows agent activity while streaming and hides it after the final response", async () => {
    const user = userEvent.setup();
    const stream = mockDeferredStreamingFetch([
      { type: "run_started", run_id: "run-1", thread_id: "conversation-test" },
      { type: "activity", activity: "Searching professor profiles" }
    ]);

    render(<App />);
    await user.type(screen.getByPlaceholderText("Ask about a topic or a BIT professor..."), "Who works on robotics?");
    await user.click(screen.getByRole("button", { name: "ASK" }));

    expect(await screen.findByText("Agent activity")).toBeInTheDocument();
    expect(screen.getByText("Searched professor profiles")).toBeInTheDocument();

    stream.enqueue({ type: "message_delta", delta: "Robotics answer." });
    stream.enqueue({ type: "run_finished", finish_reason: "completed" });
    stream.close();

    expect(await screen.findByText("Robotics answer.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Agent activity")).not.toBeInTheDocument());
  });

  it("submits the composer with Enter", async () => {
    const user = userEvent.setup();
    const fetchMock = mockStreamingFetch([
      { type: "run_started", run_id: "run-1", thread_id: "conversation-test" },
      { type: "message_delta", delta: "Submitted by keyboard." },
      { type: "run_finished", finish_reason: "completed" }
    ]);

    render(<App />);
    await user.type(screen.getByPlaceholderText("Ask about a topic or a BIT professor..."), "Keyboard question");
    await user.keyboard("{Enter}");

    expect(await screen.findByText("Keyboard question")).toBeInTheDocument();
    expect(await screen.findByText("Submitted by keyboard.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("focuses the composer when the user starts typing anywhere on the page", () => {
    render(<App />);
    const composer = screen.getByPlaceholderText("Ask about a topic or a BIT professor...");

    expect(composer).not.toHaveFocus();
    fireEvent.keyDown(document, { key: "r" });

    expect(composer).toHaveFocus();
  });

  it("sends only a bounded visible user and assistant history", async () => {
    const user = userEvent.setup();
    const messages = Array.from({ length: 14 }, (_, index) => ({
      id: `message-${index}`,
      role: index % 2 === 0 ? "user" : "assistant",
      content: `message ${index}`,
      createdAt: "2026-04-26T00:00:00.000Z",
      status: "complete",
      activity: ["Searching professor profiles"]
    }));
    localStorage.setItem(
      CHAT_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        conversationId: "conversation-test",
        updatedAt: "2026-04-26T00:00:00.000Z",
        messages
      })
    );
    const fetchMock = mockStreamingFetch([
      { type: "run_started", run_id: "run-1", thread_id: "conversation-test" },
      { type: "message_delta", delta: "Done." },
      { type: "run_finished", finish_reason: "completed" }
    ]);

    render(<App />);
    await user.type(screen.getByPlaceholderText("Ask about a topic or a BIT professor..."), "Continue");
    await user.click(screen.getByRole("button", { name: "ASK" }));

    await screen.findByText("Done.");
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(request.body as string);

    expect(body.message).toBe("Continue");
    expect(body.history).toHaveLength(12);
    expect(body.history[0]).toEqual({ role: "user", content: "message 2" });
    expect(body.history[11]).toEqual({ role: "assistant", content: "message 13" });
    expect(JSON.stringify(body.history)).not.toContain("Searching professor profiles");
  });

  it("clears the visible transcript and localStorage", async () => {
    const user = userEvent.setup();
    localStorage.setItem(
      CHAT_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        conversationId: "conversation-test",
        updatedAt: "2026-04-26T00:00:00.000Z",
        messages: [
          {
            id: "user-1",
            role: "user",
            content: "Stored question",
            createdAt: "2026-04-26T00:00:00.000Z",
            status: "complete"
          }
        ]
      })
    );

    const { container } = render(<App />);
    expect(screen.getByText("Stored question")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear chat" }));

    expect(screen.queryByText("Stored question")).not.toBeInTheDocument();
    expect(localStorage.getItem(CHAT_STORAGE_KEY)).toBeNull();
    expect(screen.getByText(/22 departments and 753 professor profiles/)).toBeInTheDocument();
    expect(screen.getByText("Try asking")).toBeInTheDocument();
    expect(container.querySelector(".quick-panel.is-conversation-active")).not.toBeInTheDocument();
  });

  it("falls back to an empty in-memory chat when localStorage is blocked", () => {
    vi.spyOn(window.localStorage, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    render(<App />);

    expect(screen.getByText(/22 departments and 753 professor profiles/)).toBeInTheDocument();
  });
});

function mockStreamingFetch(events: unknown[]) {
  const encoder = new TextEncoder();
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      new ReadableStream({
        start(controller) {
          for (const event of events) {
            controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
          }
          controller.close();
        }
      }),
      { status: 200 }
    )
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function mockDeferredStreamingFetch(initialEvents: unknown[]) {
  const encoder = new TextEncoder();
  let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
  const response = new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        streamController = controller;
        for (const event of initialEvents) {
          controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
        }
      }
    }),
    { status: 200 }
  );
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);

  return {
    close() {
      streamController?.close();
    },
    enqueue(event: unknown) {
      streamController?.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
    },
    fetchMock
  };
}
