import { KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import bitLogo from "./assets/bit-logo.png";
import professorAgentIcon from "./assets/professor-agent-icon.png";
import studentAvatarIcon from "./assets/student-avatar-icon.png";
import { AgentActivity } from "./components/AgentActivity";
import { MarkdownResponse } from "./components/MarkdownResponse";
import { streamRun, type ChatHistoryItem } from "./services/agentApi";

type QuickStart = {
  labelKey: string;
  promptKey: string;
};

type ChatRole = "user" | "assistant";

type MessageStatus = "streaming" | "complete" | "error";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  status?: MessageStatus;
  activity?: string[];
};

type StoredConversation = {
  version: 1;
  conversationId: string;
  messages: ChatMessage[];
  updatedAt: string;
};

const CHAT_STORAGE_KEY = "bit-professor-agent:conversation:v1";
const STORAGE_VERSION = 1;
const MAX_CONTEXT_MESSAGES = 12;
const GITHUB_REPOSITORY_URL = "https://github.com/khajiev13/bit-international-students";
const BIT_ISC_URL = "https://isc.bit.edu.cn/";

const quickStarts: QuickStart[] = [
  { labelKey: "quickResearch", promptKey: "quickResearchPrompt" },
  { labelKey: "quickExplain", promptKey: "quickExplainPrompt" }
];

function App() {
  const { t, i18n } = useTranslation();
  const [prompt, setPrompt] = useState("");
  const [conversation, setConversation] = useState<StoredConversation>(() => readStoredConversation());
  const [isRunning, setIsRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const language = i18n.language.startsWith("zh") ? "zh-CN" : "en";
  const canSubmit = useMemo(() => prompt.trim().length > 0 && !isRunning, [isRunning, prompt]);
  const hasMessages = conversation.messages.length > 0;
  const canClear = hasMessages || prompt.trim().length > 0 || isRunning;

  useEffect(() => {
    persistConversation(conversation);
  }, [conversation]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [conversation.updatedAt]);

  useEffect(() => {
    function handleGlobalTyping(event: globalThis.KeyboardEvent) {
      if (
        isRunning ||
        event.defaultPrevented ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.key.length !== 1 ||
        isEditableTarget(event.target)
      ) {
        return;
      }
      composerRef.current?.focus();
    }

    document.addEventListener("keydown", handleGlobalTyping, { capture: true });
    return () => document.removeEventListener("keydown", handleGlobalTyping, { capture: true });
  }, [isRunning]);

  async function handleSubmit() {
    const message = prompt.trim();
    if (!message || isRunning) {
      return;
    }

    const history = buildRecentHistory(conversation.messages);
    const userMessage = createChatMessage("user", message);
    const assistantMessage = createChatMessage("assistant", "", "streaming", []);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsRunning(true);
    setPrompt("");
    setConversation((current) => ({
      ...current,
      messages: [...current.messages, userMessage, assistantMessage],
      updatedAt: timestamp()
    }));

    try {
      await streamRun({
        threadId: conversation.conversationId,
        message,
        history,
        signal: controller.signal,
        onEvent: (agentEvent) => {
          if (agentEvent.type === "message_delta") {
            updateMessage(assistantMessage.id, (current) => ({
              ...current,
              content: `${current.content}${agentEvent.delta}`,
              status: "streaming"
            }));
          } else if (agentEvent.type === "activity") {
            updateMessage(assistantMessage.id, (current) => ({
              ...current,
              activity: [...(current.activity || []), agentEvent.activity]
            }));
          } else if (agentEvent.type === "error") {
            updateMessage(assistantMessage.id, (current) => ({
              ...current,
              content: `**${t("errorPrefix")}:** ${agentEvent.message}`,
              status: "error"
            }));
          }
        }
      });
      updateMessage(assistantMessage.id, (current) =>
        current.status === "error" ? current : { ...current, status: "complete" }
      );
    } catch (caught) {
      if ((caught as Error).name !== "AbortError") {
        updateMessage(assistantMessage.id, (current) => ({
          ...current,
          content: `**${t("errorPrefix")}:** ${
            (caught as Error).message || "Unable to reach the professor agent."
          }`,
          status: "error"
        }));
      }
    } finally {
      setIsRunning(false);
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  }

  function handleClearChat() {
    abortRef.current?.abort();
    abortRef.current = null;
    clearStoredConversation();
    setPrompt("");
    setIsRunning(false);
    setConversation(createConversation());
  }

  function updateMessage(messageId: string, updater: (message: ChatMessage) => ChatMessage) {
    setConversation((current) => {
      let changed = false;
      const messages = current.messages.map((message) => {
        if (message.id !== messageId) {
          return message;
        }
        changed = true;
        return updater(message);
      });
      if (!changed) {
        return current;
      }
      return { ...current, messages, updatedAt: timestamp() };
    });
  }

  return (
    <main className={`app ${hasMessages ? "is-chatting" : ""}`}>
      <section className="title-band">
        <div className="title-copy">
          <div className="title-row">
            <div className="title-heading">
              <div className="title-text">
                <h1>{t("title")}</h1>
                <p className="project-kicker">{t("projectKicker")}</p>
              </div>
              <img className="title-logo" alt="BIT logo" src={bitLogo} />
            </div>
            <div className="title-actions">
              <a
                aria-label={t("iscLabel")}
                className="title-link official-link"
                href={BIT_ISC_URL}
                rel="noreferrer"
                target="_blank"
                title={t("iscLabel")}
              >
                {t("iscLink")}
              </a>
              <a
                aria-label={t("githubLabel")}
                className="title-link github-link"
                href={GITHUB_REPOSITORY_URL}
                rel="noreferrer"
                target="_blank"
                title={t("githubLabel")}
              >
                {t("githubLink")}
              </a>
              <div className="language-switch" aria-label="Change language">
                <button
                  className={language === "en" ? "active" : ""}
                  type="button"
                  onClick={() => i18n.changeLanguage("en")}
                >
                  EN
                </button>
                <button
                  className={language === "zh-CN" ? "active" : ""}
                  type="button"
                  onClick={() => i18n.changeLanguage("zh-CN")}
                >
                  中文
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="workspace">
        <div className={`agent-window ${hasMessages ? "has-messages" : ""}`} aria-label="BIT professor agent app">
          <aside className="side">
            <div className="agent-identity">
              <div className="seal">BIT</div>
              <div>
                <h2>{t("agentTitle")}</h2>
                <p>{t("agentSubtitle")}</p>
                <p className="support-note">{t("githubSupportNote")}</p>
              </div>
            </div>

            <div className={`quick-panel ${hasMessages ? "is-conversation-active" : ""}`}>
              <strong className="quick-title">{t("capabilitiesTitle")}</strong>
              <div className="quick-starts">
                {quickStarts.map((quickStart) => (
                  <button
                    className="quick-start"
                    key={quickStart.labelKey}
                    type="button"
                    onClick={() => setPrompt(t(quickStart.promptKey))}
                  >
                    <span>{t(quickStart.labelKey)}</span>
                    <small>{t(quickStart.promptKey)}</small>
                  </button>
                ))}
              </div>
            </div>
          </aside>

          <section className="main">
            <div className="conversation-panel">
              {!hasMessages ? (
                <div className="welcome">
                  <div className="agent-dot">
                    <img alt="" src={professorAgentIcon} />
                  </div>
                  <div className="welcome-message">
                    <strong>{t("welcomeKicker")}</strong>
                    <p>{t("welcome")}</p>
                  </div>
                </div>
              ) : null}

              {hasMessages ? (
                <section className="conversation" aria-label={t("conversationLabel")}>
                  {conversation.messages.map((chatMessage) => (
                    <article
                      className={`chat-message ${chatMessage.role}`}
                      data-testid={`chat-message-${chatMessage.role}`}
                      key={chatMessage.id}
                    >
                      <div className="message-avatar" aria-hidden="true">
                        <img
                          alt=""
                          src={chatMessage.role === "assistant" ? professorAgentIcon : studentAvatarIcon}
                        />
                      </div>
                      <div className="message-card">
                        <strong className="message-author">
                          {chatMessage.role === "assistant" ? t("assistantLabel") : t("youLabel")}
                        </strong>
                        {shouldShowActivity(chatMessage) ? (
                          <AgentActivity
                            hasResponse={chatMessage.content.trim().length > 0}
                            items={chatMessage.activity || []}
                            locale={language}
                            status={chatMessage.status}
                            title={t("activityTitle")}
                          />
                        ) : null}
                        {chatMessage.role === "assistant" ? (
                          chatMessage.content.trim().length > 0 ? (
                            <MarkdownResponse markdown={chatMessage.content} />
                          ) : (
                            <p className="assistant-thinking">{t("thinking")}</p>
                          )
                        ) : (
                          <p className="user-message-text">{chatMessage.content}</p>
                        )}
                      </div>
                    </article>
                  ))}
                  <div ref={messagesEndRef} />
                </section>
              ) : null}
            </div>

            <div className="composer" role="group" aria-label="Professor agent composer">
              <label className="sr-only" htmlFor="professor-agent-prompt">
                {t("composerPlaceholder")}
              </label>
              <textarea
                id="professor-agent-prompt"
                className="input"
                disabled={isRunning}
                maxLength={2000}
                onChange={(event) => setPrompt(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder={t("composerPlaceholder")}
                ref={composerRef}
                rows={1}
                value={prompt}
              />
              <div className="composer-actions">
                <button
                  className="clear-chat"
                  disabled={!canClear}
                  type="button"
                  onClick={handleClearChat}
                  onMouseDown={(event) => event.preventDefault()}
                >
                  {t("clearChat")}
                </button>
                <button
                  className="ask"
                  disabled={!canSubmit}
                  type="button"
                  onClick={() => void handleSubmit()}
                  onMouseDown={(event) => event.preventDefault()}
                >
                  {isRunning ? t("working") : t("ask")}
                </button>
              </div>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}

function buildRecentHistory(messages: ChatMessage[]): ChatHistoryItem[] {
  return messages
    .filter((message) => message.content.trim().length > 0)
    .filter((message) => message.role === "user" || message.status !== "error")
    .map((message) => ({ role: message.role, content: message.content }))
    .slice(-MAX_CONTEXT_MESSAGES);
}

function readStoredConversation(): StoredConversation {
  if (typeof window === "undefined") {
    return createConversation();
  }

  try {
    const raw = window.localStorage.getItem(CHAT_STORAGE_KEY);
    if (!raw) {
      return createConversation();
    }

    const parsed = JSON.parse(raw) as Partial<StoredConversation>;
    if (
      parsed.version !== STORAGE_VERSION ||
      typeof parsed.conversationId !== "string" ||
      !Array.isArray(parsed.messages)
    ) {
      return createConversation();
    }

    const messages = parsed.messages
      .map((message) => normalizeStoredMessage(message))
      .filter((message): message is ChatMessage => message !== null);

    return {
      version: STORAGE_VERSION,
      conversationId: parsed.conversationId,
      messages,
      updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : timestamp()
    };
  } catch {
    return createConversation();
  }
}

function persistConversation(conversation: StoredConversation) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    if (conversation.messages.length === 0) {
      window.localStorage.removeItem(CHAT_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(conversation));
  } catch {
    // localStorage can be blocked; the in-memory chat state still works.
  }
}

function clearStoredConversation() {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.removeItem(CHAT_STORAGE_KEY);
  } catch {
    // Ignore storage failures so Clear chat still resets visible state.
  }
}

function normalizeStoredMessage(value: unknown): ChatMessage | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as Partial<ChatMessage>;
  if (!isChatRole(candidate.role) || typeof candidate.content !== "string") {
    return null;
  }

  const content = candidate.content;
  if (content.trim().length === 0) {
    return null;
  }

  return {
    id: typeof candidate.id === "string" ? candidate.id : createId(candidate.role),
    role: candidate.role,
    content,
    createdAt: typeof candidate.createdAt === "string" ? candidate.createdAt : timestamp(),
    status: normalizeStatus(candidate.status),
    activity: Array.isArray(candidate.activity)
      ? candidate.activity.filter((item): item is string => typeof item === "string")
      : undefined
  };
}

function normalizeStatus(status: unknown): MessageStatus | undefined {
  if (status === "error") {
    return "error";
  }
  if (status === "streaming" || status === "complete") {
    return "complete";
  }
  return undefined;
}

function isChatRole(role: unknown): role is ChatRole {
  return role === "user" || role === "assistant";
}

function shouldShowActivity(message: ChatMessage): boolean {
  return (
    message.role === "assistant" &&
    Boolean(message.activity?.length) &&
    (message.status === "streaming" || message.status === "error")
  );
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  return Boolean(
    target.closest("input, textarea, select, [contenteditable='true'], [contenteditable='']")
  );
}

function createConversation(): StoredConversation {
  return {
    version: STORAGE_VERSION,
    conversationId: createId("conversation"),
    messages: [],
    updatedAt: timestamp()
  };
}

function createChatMessage(
  role: ChatRole,
  content: string,
  status: MessageStatus = "complete",
  activity?: string[]
): ChatMessage {
  return {
    id: createId(role),
    role,
    content,
    createdAt: timestamp(),
    status,
    activity
  };
}

function createId(prefix: string): string {
  const randomId = globalThis.crypto?.randomUUID?.();
  return randomId ? `${prefix}-${randomId}` : `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function timestamp(): string {
  return new Date().toISOString();
}

export default App;
