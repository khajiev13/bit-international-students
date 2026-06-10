from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from deepagents.backends import ContextHubBackend
from langchain.agents.middleware.types import AgentMiddleware

from app.config import Settings
from app.corpus import ProfessorCorpus
from app.prompts import build_deep_agent_system_prompt
from app.question_answer_log import QuestionAnswerLog
from app.schemas import HistoryMessage, StreamEvent
from app.tools import SAFE_TOOL_NAMES

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


class FixedSystemPromptMiddleware(AgentMiddleware[Any, Any, Any]):
    def __init__(self, system_prompt: str) -> None:
        self._system_prompt = system_prompt

    def wrap_model_call(
        self,
        request: "ModelRequest[Any]",
        handler: Callable[["ModelRequest[Any]"], "ModelResponse[Any]"],
    ) -> "ModelResponse[Any]":
        return handler(request.override(system_prompt=self._system_prompt))

    async def awrap_model_call(
        self,
        request: "ModelRequest[Any]",
        handler: Callable[["ModelRequest[Any]"], Awaitable["ModelResponse[ResponseT]"]],
    ) -> "ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]":
        return await handler(request.override(system_prompt=self._system_prompt))


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
            for attempt_index in range(2):
                try:
                    graph_run_id = run_id if attempt_index == 0 else f"{run_id}:retry:{attempt_index}"
                    async for event in self._stream_agent_events(
                        agent=agent,
                        thread_id=thread_id,
                        run_id=graph_run_id,
                        message=message,
                        history=history or [],
                    ):
                        if event.type == "message_delta":
                            yielded_text = True
                            if event.delta:
                                answer_parts.append(event.delta)
                        yield _encode_event(event.model_copy(update={"run_id": run_id, "thread_id": thread_id}))
                    break
                except Exception as exc:
                    if attempt_index == 0 and not yielded_text and _is_transient_model_stream_error(exc):
                        logger.warning("Transient model stream read failed before answer text; retrying.", exc_info=True)
                        yield _encode_event(
                            StreamEvent(
                                type="activity",
                                run_id=run_id,
                                thread_id=thread_id,
                                activity="Retrying model connection",
                            )
                        )
                        continue
                    raise
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

        system_prompt = build_deep_agent_system_prompt(context_hub_configured=self._settings.context_hub_configured)
        _register_pure_file_reading_harness_profile(base_system_prompt=system_prompt)
        backend = _build_agent_backend(
            profiles_dir=self._corpus.profiles_dir,
            settings=self._settings,
        )
        model = ChatOpenAI(
            model=self._settings.llm_model,
            api_key=self._settings.llm_api_key.get_secret_value() if self._settings.llm_api_key else None,
            base_url=self._settings.llm_base_url,
            temperature=0,
        )
        return create_deep_agent(
            model=model,
            tools=[],
            system_prompt=None,
            middleware=[
                AllowListedToolsMiddleware(SAFE_TOOL_NAMES),
                FixedSystemPromptMiddleware(system_prompt),
            ],
            subagents=[],
            permissions=_filesystem_permissions(
                FilesystemPermission,
                context_hub_configured=self._settings.context_hub_configured,
            ),
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
        config["recursion_limit"] = self._settings.agent_recursion_limit

        if hasattr(agent, "astream_events"):
            translator = LangChainStreamTranslator()
            async for raw_event in agent.astream_events(input_state, config=config, version="v2"):
                for event in translator.events_from(raw_event):
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


class LangChainStreamTranslator:
    def __init__(self) -> None:
        self._model_buffers: dict[str, list[str]] = {}

    def events_from(self, raw_event: dict[str, Any]) -> list[StreamEvent]:
        event_name = raw_event.get("event")
        tool_name = str(raw_event.get("name") or "")
        if event_name == "on_tool_start" and tool_name in SAFE_ACTIVITY_BY_TOOL:
            return [StreamEvent(type="activity", activity=SAFE_ACTIVITY_BY_TOOL[tool_name])]

        if event_name == "on_chat_model_stream":
            delta = _content_to_text(raw_event.get("data", {}).get("chunk"))
            if delta:
                self._model_buffers.setdefault(_event_run_id(raw_event), []).append(delta)
            return []

        if event_name == "on_chat_model_end":
            model_run_id = _event_run_id(raw_event)
            text = "".join(self._model_buffers.pop(model_run_id, []))
            output = raw_event.get("data", {}).get("output")
            if not text:
                text = _content_to_text(output)
            if text and not _message_has_tool_calls(output):
                return [StreamEvent(type="message_delta", delta=text)]
        return []


def _event_run_id(raw_event: dict[str, Any]) -> str:
    return str(raw_event.get("run_id") or "__default__")


def _message_has_tool_calls(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("tool_calls") or value.get("tool_call_chunks") or value.get("invalid_tool_calls"))

    for attr in ("tool_calls", "tool_call_chunks", "invalid_tool_calls"):
        if getattr(value, attr, None):
            return True

    additional_kwargs = getattr(value, "additional_kwargs", None)
    return isinstance(additional_kwargs, dict) and bool(additional_kwargs.get("tool_calls"))


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


def _is_transient_model_stream_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if current.__class__.__name__ in {"ReadError", "RemoteProtocolError"} and current.__class__.__module__.startswith(("httpx", "httpcore")):
            return True
        current = current.__cause__ or current.__context__
    return False


def _register_pure_file_reading_harness_profile(
    *,
    base_system_prompt: str,
    key: str = "openai",
) -> None:
    from deepagents import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile

    register_harness_profile(
        key,
        HarnessProfile(
            base_system_prompt=base_system_prompt,
            excluded_tools=frozenset({"write_file", "edit_file", "execute", "task"}),
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )


def _build_agent_backend(*, profiles_dir: Path, settings: Settings) -> Any:
    from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend

    routes: dict[str, Any] = {
        "/professors/": FilesystemBackend(root_dir=profiles_dir, virtual_mode=True),
    }
    if settings.context_hub_configured:
        routes["/wiki/"] = _build_context_hub_backend(settings)

    return CompositeBackend(
        default=StateBackend(),
        routes=routes,
    )


def _build_context_hub_backend(settings: Settings) -> Any:
    from langsmith import Client

    api_key = settings.langsmith_api_key.get_secret_value() if settings.langsmith_api_key else None
    return ContextHubBackend(
        settings.context_hub_identifier,
        client=Client(api_url=settings.langsmith_endpoint, api_key=api_key),
    )


def _filesystem_permissions(
    filesystem_permission_cls: type[Any] | None = None,
    *,
    context_hub_configured: bool = False,
) -> list[Any]:
    if filesystem_permission_cls is None:
        from deepagents import FilesystemPermission

        filesystem_permission_cls = FilesystemPermission

    allowed_read_paths = [
        "/",
        "/professors",
        "/professors/**",
        "/large_tool_results",
        "/large_tool_results/**",
        "/conversation_history",
        "/conversation_history/**",
    ]
    if context_hub_configured:
        allowed_read_paths.extend(["/wiki", "/wiki/**"])

    rules = [
        filesystem_permission_cls(operations=["read", "write"], paths=["/**/.*"], mode="deny"),
        filesystem_permission_cls(
            operations=["read"],
            paths=allowed_read_paths,
            mode="allow",
        ),
        filesystem_permission_cls(operations=["write"], paths=["/professors", "/professors/**"], mode="deny"),
    ]
    if context_hub_configured:
        rules.append(filesystem_permission_cls(operations=["write"], paths=["/wiki", "/wiki/**"], mode="deny"))
    rules.append(
        filesystem_permission_cls(operations=["read", "write"], paths=["/**"], mode="deny")
    )
    return rules


def _encode_event(event: StreamEvent) -> str:
    return json.dumps(event.model_dump(exclude_none=True), ensure_ascii=False) + "\n"


def _log_background_question_answer_error(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("Failed to write question-answer log row.")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
