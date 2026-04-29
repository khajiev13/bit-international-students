from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.types import AgentMiddleware

from app.config import Settings
from app.corpus import ProfessorCorpus
from app.prompts import DEEP_AGENT_SYSTEM_PROMPT
from app.question_answer_log import QuestionAnswerLog
from app.schemas import HistoryMessage, StreamEvent
from app.tools import SAFE_TOOL_NAMES, ProfessorToolFactory

if TYPE_CHECKING:
    from langchain.agents.middleware.types import ExtendedModelResponse, ModelRequest, ModelResponse, ResponseT
    from langchain_core.messages import AIMessage
    from langchain_core.tools import BaseTool


SAFE_ACTIVITY_BY_TOOL = {
    "write_todos": "Updating the agent todo list",
    "ls": "Listing support files",
    "read_file": "Reading a support file",
    "glob": "Finding support files",
    "grep": "Searching support files",
    "write_file": "Writing a scratch file",
    "edit_file": "Editing a scratch file",
    "list_departments": "Listing departments",
    "read_department_index": "Reading a department index",
    "list_professors": "Listing professor profiles",
    "search_professors": "Searching professor profiles",
    "read_professor_profile": "Reading a professor profile",
    "compare_professors": "Reviewing selected professor profiles",
}

logger = logging.getLogger(__name__)


class AllowListedToolsMiddleware(AgentMiddleware[Any, Any, Any]):
    def __init__(self, allowed_tools: frozenset[str]) -> None:
        self._allowed_tools = allowed_tools

    def wrap_model_call(
        self,
        request: "ModelRequest[Any]",
        handler: Callable[["ModelRequest[Any]"], "ModelResponse[Any]"],
    ) -> "ModelResponse[Any]":
        return handler(request.override(tools=self._filter_tools(request.tools)))

    async def awrap_model_call(
        self,
        request: "ModelRequest[Any]",
        handler: Callable[["ModelRequest[Any]"], Awaitable["ModelResponse[ResponseT]"]],
    ) -> "ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]":
        return await handler(request.override(tools=self._filter_tools(request.tools)))

    def _filter_tools(self, tools: list["BaseTool | dict[str, Any]"]) -> list["BaseTool | dict[str, Any]"]:
        return [tool for tool in tools if _tool_name(tool) in self._allowed_tools]


class AgentSessionStore:
    def __init__(self) -> None:
        self._versions: dict[str, int] = {}

    def create(self) -> str:
        thread_id = uuid.uuid4().hex
        self._versions[thread_id] = 0
        return thread_id

    def ensure(self, thread_id: str) -> None:
        self._versions.setdefault(thread_id, 0)

    def reset(self, thread_id: str) -> None:
        self._versions[thread_id] = self._versions.get(thread_id, 0) + 1

    def config_for(self, thread_id: str, run_id: str | None = None) -> dict[str, Any]:
        self.ensure(thread_id)
        graph_thread_id = thread_id if run_id is None else f"{thread_id}:run:{run_id}"
        return {
            "configurable": {
                "thread_id": graph_thread_id,
                "checkpoint_ns": f"reset-{self._versions[thread_id]}",
            }
        }


class ProfessorAgentService:
    def __init__(
        self,
        *,
        settings: Settings,
        corpus: ProfessorCorpus,
        question_answer_log: QuestionAnswerLog | None = None,
    ) -> None:
        self._settings = settings
        self._corpus = corpus
        self._question_answer_log = question_answer_log
        self._sessions = AgentSessionStore()
        self._agent: Any | None = None
        self._agent_lock = asyncio.Lock()
        self._background_log_tasks: set[asyncio.Task[None]] = set()

    @property
    def sessions(self) -> AgentSessionStore:
        return self._sessions

    async def stream_run(
        self,
        *,
        thread_id: str,
        message: str,
        history: list[HistoryMessage] | None = None,
    ) -> AsyncIterator[str]:
        run_id = uuid.uuid4().hex
        created_at = _utc_now()
        yield _encode_event(StreamEvent(type="run_started", run_id=run_id, thread_id=thread_id))

        if not self._settings.model_configured:
            error_message = "Model credentials are not configured."
            yield _encode_event(
                StreamEvent(
                    type="error",
                    run_id=run_id,
                    thread_id=thread_id,
                    message=error_message,
                )
            )
            self._schedule_question_answer_log(
                thread_id=thread_id,
                run_id=run_id,
                question=message,
                answer=error_message,
                status="configuration_error",
                created_at=created_at,
            )
            yield _encode_event(StreamEvent(type="run_finished", run_id=run_id, thread_id=thread_id, finish_reason="configuration_error"))
            return

        answer_parts: list[str] = []
        try:
            agent = await self._get_agent()
            yielded_text = False
            async for event in self._stream_agent_events(
                agent=agent,
                thread_id=thread_id,
                run_id=run_id,
                message=message,
                history=history or [],
            ):
                if event.type == "message_delta":
                    yielded_text = True
                    if event.delta:
                        answer_parts.append(event.delta)
                yield _encode_event(event.model_copy(update={"run_id": run_id, "thread_id": thread_id}))
            if not yielded_text:
                fallback_message = "I could not produce a response for this professor-corpus question."
                answer_parts.append(fallback_message)
                yield _encode_event(
                    StreamEvent(
                        type="message_delta",
                        run_id=run_id,
                        thread_id=thread_id,
                        delta=fallback_message,
                    )
                )
            self._schedule_question_answer_log(
                thread_id=thread_id,
                run_id=run_id,
                question=message,
                answer="".join(answer_parts),
                status="completed",
                created_at=created_at,
            )
            yield _encode_event(StreamEvent(type="run_finished", run_id=run_id, thread_id=thread_id, finish_reason="completed"))
        except Exception:
            error_message = "The run could not be completed safely."
            logger.exception("Professor agent run failed.")
            self._schedule_question_answer_log(
                thread_id=thread_id,
                run_id=run_id,
                question=message,
                answer=error_message,
                status="error",
                created_at=created_at,
            )
            yield _encode_event(
                StreamEvent(
                    type="error",
                    run_id=run_id,
                    thread_id=thread_id,
                    message=error_message,
                )
            )
            yield _encode_event(StreamEvent(type="run_finished", run_id=run_id, thread_id=thread_id, finish_reason="error"))

    def _schedule_question_answer_log(
        self,
        *,
        thread_id: str,
        run_id: str,
        question: str,
        answer: str,
        status: str,
        created_at: str,
    ) -> None:
        if self._question_answer_log is None:
            return

        finished_at = _utc_now()
        task = asyncio.create_task(
            asyncio.to_thread(
                self._question_answer_log.record_run,
                thread_id=thread_id,
                run_id=run_id,
                question=question,
                answer=answer,
                status=status,
                created_at=created_at,
                finished_at=finished_at,
            )
        )
        task.add_done_callback(_log_background_question_answer_error)
        task.add_done_callback(self._background_log_tasks.discard)
        self._background_log_tasks.add(task)

    async def _get_agent(self) -> Any:
        if self._agent is not None:
            return self._agent
        async with self._agent_lock:
            if self._agent is None:
                self._agent = self._build_agent()
        return self._agent

    def _build_agent(self) -> Any:
        from deepagents import FilesystemPermission, create_deep_agent
        from langchain_openai import ChatOpenAI
        from langgraph.checkpoint.memory import InMemorySaver

        tools = ProfessorToolFactory(self._corpus).build()
        backend = _build_agent_backend(
            profiles_dir=self._corpus.profiles_dir,
            scratch_dir=self._settings.agent_scratch_dir,
        )
        model = ChatOpenAI(
            model=self._settings.llm_model,
            api_key=self._settings.llm_api_key.get_secret_value() if self._settings.llm_api_key else None,
            base_url=self._settings.llm_base_url,
            temperature=0,
        )
        return create_deep_agent(
            model=model,
            tools=tools,
            system_prompt=DEEP_AGENT_SYSTEM_PROMPT,
            middleware=[AllowListedToolsMiddleware(SAFE_TOOL_NAMES)],
            permissions=_filesystem_permissions(FilesystemPermission),
            backend=backend,
            checkpointer=InMemorySaver(),
        )

    async def _stream_agent_events(
        self,
        *,
        agent: Any,
        thread_id: str,
        run_id: str,
        message: str,
        history: list[HistoryMessage],
    ) -> AsyncIterator[StreamEvent]:
        input_state = {"messages": [*self._bounded_history(history), {"role": "user", "content": message}]}
        config = self._sessions.config_for(thread_id, run_id=run_id)

        if hasattr(agent, "astream_events"):
            async for raw_event in agent.astream_events(input_state, config=config, version="v2"):
                event = _event_from_langchain(raw_event)
                if event is not None:
                    yield event
            return

        result = await agent.ainvoke(input_state, config=config)
        text = _extract_final_text(result)
        if text:
            yield StreamEvent(type="message_delta", delta=text)

    def _bounded_history(self, history: list[HistoryMessage]) -> list[dict[str, str]]:
        if self._settings.max_history_messages <= 0 or self._settings.max_history_chars <= 0:
            return []

        messages = [
            {"role": item.role, "content": item.content.strip()}
            for item in history
            if item.content.strip()
        ][-self._settings.max_history_messages :]

        while len(messages) > 1 and _history_char_count(messages) > self._settings.max_history_chars:
            messages.pop(0)

        if messages and _history_char_count(messages) > self._settings.max_history_chars:
            messages[0]["content"] = messages[0]["content"][-self._settings.max_history_chars :]

        return messages


def _tool_name(tool: "BaseTool | dict[str, Any]") -> str | None:
    if isinstance(tool, dict):
        name = tool.get("name")
        return name if isinstance(name, str) else None
    name = getattr(tool, "name", None)
    return name if isinstance(name, str) else None


def _event_from_langchain(raw_event: dict[str, Any]) -> StreamEvent | None:
    event_name = raw_event.get("event")
    tool_name = str(raw_event.get("name") or "")
    if event_name == "on_tool_start" and tool_name in SAFE_ACTIVITY_BY_TOOL:
        return StreamEvent(type="activity", activity=SAFE_ACTIVITY_BY_TOOL[tool_name])
    if event_name == "on_chat_model_stream":
        delta = _content_to_text(raw_event.get("data", {}).get("chunk"))
        if delta:
            return StreamEvent(type="message_delta", delta=delta)
    return None


def _extract_final_text(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    messages = result.get("messages") or []
    if not messages:
        return ""
    return _content_to_text(messages[-1])


def _content_to_text(value: Any) -> str:
    content = getattr(value, "content", value)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _history_char_count(messages: list[dict[str, str]]) -> int:
    return sum(len(message["content"]) for message in messages)


def _build_agent_backend(*, profiles_dir: Path, scratch_dir: Path) -> Any:
    from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend

    scratch_dir.mkdir(parents=True, exist_ok=True)
    return CompositeBackend(
        default=StateBackend(),
        routes={
            "/professors/": FilesystemBackend(root_dir=profiles_dir, virtual_mode=True),
            "/scratch/": FilesystemBackend(root_dir=scratch_dir, virtual_mode=True),
        },
    )


def _filesystem_permissions(filesystem_permission_cls: type[Any] | None = None) -> list[Any]:
    if filesystem_permission_cls is None:
        from deepagents import FilesystemPermission

        filesystem_permission_cls = FilesystemPermission

    return [
        filesystem_permission_cls(
            operations=["read"],
            paths=["/", "/professors", "/professors/**", "/scratch", "/scratch/**"],
            mode="allow",
        ),
        filesystem_permission_cls(operations=["write"], paths=["/scratch", "/scratch/**"], mode="allow"),
        filesystem_permission_cls(operations=["write"], paths=["/professors", "/professors/**"], mode="deny"),
        filesystem_permission_cls(operations=["read", "write"], paths=["/**", "/**/.*"], mode="deny"),
    ]


def _encode_event(event: StreamEvent) -> str:
    return json.dumps(event.model_dump(exclude_none=True), ensure_ascii=False) + "\n"


def _log_background_question_answer_error(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except Exception:
        logger.exception("Failed to write question-answer log row.")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
