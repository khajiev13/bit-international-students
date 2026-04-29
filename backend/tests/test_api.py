import json
import time

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.main import create_app
from app.question_answer_log import QuestionAnswerLog


class FakeChunk:
    content = "Li Xin works on machine learning."


class FakeAgent:
    def __init__(self) -> None:
        self.calls = []

    async def astream_events(self, input_state, *, config, version):
        self.calls.append({"input_state": input_state, "config": config, "version": version})
        yield {"event": "on_tool_start", "name": "write_todos", "data": {"input": "private planning"}}
        yield {"event": "on_tool_start", "name": "read_file", "data": {"input": "/professors/index.md"}}
        yield {"event": "on_tool_start", "name": "write_file", "data": {"input": "/scratch/search-notes.md"}}
        yield {"event": "on_tool_start", "name": "search_professors", "data": {"input": "/Users/private/.env"}}
        yield {"event": "on_tool_start", "name": "execute", "data": {"input": "cat /Users/private/.env"}}
        yield {"event": "on_chat_model_stream", "data": {"chunk": FakeChunk()}}


def wait_for_log_rows(log: QuestionAnswerLog, expected_count: int, *, timeout_seconds: float = 2.0):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        rows = log.list_recent(limit=10)
        if len(rows) >= expected_count:
            return rows
        time.sleep(0.01)
    return log.list_recent(limit=10)


def test_professor_api_endpoints() -> None:
    client = TestClient(create_app())

    ready = client.get("/readyz").json()
    assert ready["status"] == "ready"
    assert ready["department_count"] == 22
    assert ready["professor_count"] == 753

    departments = client.get("/api/departments").json()
    assert len(departments) == 22
    assert any(department["slug"] == "computer-science-and-technology" for department in departments)

    professors = client.get("/api/professors").json()
    assert len(professors) == 753

    cs_professors = client.get("/api/professors", params={"department_slug": "computer-science-and-technology"}).json()
    assert len(cs_professors) == 60
    li_xin_summary = next(professor for professor in cs_professors if professor["profile_id"] == "computer-science-and-technology/li-xin")
    assert li_xin_summary["detail_url"] == "https://isc.bit.edu.cn/schools/csat/knowingprofessors5/b186322.htm"
    assert client.get("/api/departments/computer-science-and-technology/index").json()["department"]["professor_count"] == 60
    li_xin_profile = client.get("/api/professors/computer-science-and-technology/li-xin").json()
    assert li_xin_profile["name"] == "LI Xin"
    assert li_xin_profile["detail_url"] == li_xin_summary["detail_url"]
    assert client.get("/api/professors/li-xin").status_code == 404
    assert client.get("/api/professors/..%2Fpyproject.toml").status_code == 404


def test_stream_does_not_pre_guard_unrelated_prompts() -> None:
    app = create_app()
    app.state.settings.llm_api_key = SecretStr("test-key")
    fake_agent = FakeAgent()

    async def fake_get_agent():
        return fake_agent

    app.state.agent_service._get_agent = fake_get_agent
    client = TestClient(app)
    thread_id = client.post("/api/sessions").json()["thread_id"]

    with client.stream(
        "POST",
        f"/api/sessions/{thread_id}/runs/stream",
        json={"message": "Plan a vacation to Paris"},
    ) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]

    assert [event["type"] for event in events] == [
        "run_started",
        "activity",
        "activity",
        "activity",
        "activity",
        "message_delta",
        "run_finished",
    ]
    assert events[-1]["finish_reason"] == "completed"


def test_stream_activity_is_sanitized_for_valid_run() -> None:
    app = create_app()
    app.state.settings.llm_api_key = SecretStr("test-key")
    fake_agent = FakeAgent()

    async def fake_get_agent():
        return fake_agent

    app.state.agent_service._get_agent = fake_get_agent
    client = TestClient(app)
    thread_id = client.post("/api/sessions").json()["thread_id"]

    with client.stream(
        "POST",
        f"/api/sessions/{thread_id}/runs/stream",
        json={"message": "Which BIT professors work on machine learning?"},
    ) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]

    activities = [event.get("activity") for event in events if event["type"] == "activity"]
    serialized = json.dumps(events)
    assert activities == [
        "Updating the agent todo list",
        "Reading a support file",
        "Writing a scratch file",
        "Searching professor profiles",
    ]
    assert "execute" not in serialized
    assert "/Users/private" not in serialized
    assert events[-1]["finish_reason"] == "completed"


def test_stream_accepts_visible_history_and_current_message() -> None:
    app = create_app()
    app.state.settings.llm_api_key = SecretStr("test-key")
    fake_agent = FakeAgent()

    async def fake_get_agent():
        return fake_agent

    app.state.agent_service._get_agent = fake_get_agent
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/sessions/frontend-conversation/runs/stream",
        json={
            "message": "Now compare them.",
            "history": [
                {"role": "user", "content": "Who works on machine learning?"},
                {"role": "assistant", "content": "Li Xin works on machine learning."},
            ],
        },
    ) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]

    assert events[-1]["finish_reason"] == "completed"
    assert fake_agent.calls[0]["input_state"]["messages"] == [
        {"role": "user", "content": "Who works on machine learning?"},
        {"role": "assistant", "content": "Li Xin works on machine learning."},
        {"role": "user", "content": "Now compare them."},
    ]


def test_repeated_runs_use_isolated_graph_threads() -> None:
    app = create_app()
    app.state.settings.llm_api_key = SecretStr("test-key")
    fake_agent = FakeAgent()

    async def fake_get_agent():
        return fake_agent

    app.state.agent_service._get_agent = fake_get_agent
    client = TestClient(app)
    thread_id = "frontend-conversation"

    for message in ["First question", "Second question"]:
        with client.stream(
            "POST",
            f"/api/sessions/{thread_id}/runs/stream",
            json={"message": message},
        ) as response:
            assert response.status_code == 200
            [json.loads(line) for line in response.iter_lines() if line]

    graph_thread_ids = [call["config"]["configurable"]["thread_id"] for call in fake_agent.calls]
    assert len(graph_thread_ids) == 2
    assert graph_thread_ids[0] != graph_thread_ids[1]
    assert all(graph_thread_id.startswith(f"{thread_id}:run:") for graph_thread_id in graph_thread_ids)


def test_history_is_bounded_before_agent_call() -> None:
    app = create_app()
    app.state.settings.llm_api_key = SecretStr("test-key")
    app.state.settings.max_history_messages = 2
    app.state.settings.max_history_chars = 12
    fake_agent = FakeAgent()

    async def fake_get_agent():
        return fake_agent

    app.state.agent_service._get_agent = fake_get_agent
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/sessions/frontend-conversation/runs/stream",
        json={
            "message": "Current",
            "history": [
                {"role": "user", "content": "Older message"},
                {"role": "assistant", "content": "Recent assistant response"},
                {"role": "user", "content": "Recent user message"},
            ],
        },
    ) as response:
        assert response.status_code == 200
        [json.loads(line) for line in response.iter_lines() if line]

    assert fake_agent.calls[0]["input_state"]["messages"] == [
        {"role": "user", "content": "user message"},
        {"role": "user", "content": "Current"},
    ]


def test_stream_records_completed_question_answer_asynchronously(tmp_path) -> None:
    app = create_app()
    app.state.settings.llm_api_key = SecretStr("test-key")
    app.state.question_answer_log = QuestionAnswerLog(tmp_path / "qa.sqlite3")
    app.state.agent_service._question_answer_log = app.state.question_answer_log
    fake_agent = FakeAgent()

    async def fake_get_agent():
        return fake_agent

    app.state.agent_service._get_agent = fake_get_agent
    client = TestClient(app)
    thread_id = client.post("/api/sessions").json()["thread_id"]

    with client.stream(
        "POST",
        f"/api/sessions/{thread_id}/runs/stream",
        json={"message": "Which professors work on machine learning?"},
    ) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]

    rows = wait_for_log_rows(app.state.question_answer_log, 1)
    assert len(rows) == 1
    assert rows[0]["thread_id"] == thread_id
    assert rows[0]["question"] == "Which professors work on machine learning?"
    assert rows[0]["answer"] == "Li Xin works on machine learning."
    assert rows[0]["status"] == "completed"
    assert rows[0]["run_id"] == events[0]["run_id"]


def test_stream_records_configuration_error_question_answer_asynchronously(tmp_path) -> None:
    app = create_app()
    app.state.settings.llm_api_key = None
    app.state.question_answer_log = QuestionAnswerLog(tmp_path / "qa.sqlite3")
    app.state.agent_service._question_answer_log = app.state.question_answer_log
    client = TestClient(app)
    thread_id = client.post("/api/sessions").json()["thread_id"]

    with client.stream(
        "POST",
        f"/api/sessions/{thread_id}/runs/stream",
        json={"message": "Who works on robotics?"},
    ) as response:
        assert response.status_code == 200
        [json.loads(line) for line in response.iter_lines() if line]

    rows = wait_for_log_rows(app.state.question_answer_log, 1)
    assert len(rows) == 1
    assert rows[0]["question"] == "Who works on robotics?"
    assert rows[0]["answer"] == "Model credentials are not configured."
    assert rows[0]["status"] == "configuration_error"


def test_stream_continues_when_async_question_answer_log_write_fails() -> None:
    class FailingQuestionAnswerLog:
        def record_run(
            self,
            *,
            thread_id: str,
            run_id: str,
            question: str,
            answer: str,
            status: str,
            created_at: str | None = None,
            finished_at: str | None = None,
        ) -> None:
            raise OSError("database unavailable")

    app = create_app()
    app.state.settings.llm_api_key = SecretStr("test-key")
    app.state.question_answer_log = FailingQuestionAnswerLog()
    app.state.agent_service._question_answer_log = app.state.question_answer_log
    fake_agent = FakeAgent()

    async def fake_get_agent():
        return fake_agent

    app.state.agent_service._get_agent = fake_get_agent
    client = TestClient(app)
    thread_id = client.post("/api/sessions").json()["thread_id"]

    with client.stream(
        "POST",
        f"/api/sessions/{thread_id}/runs/stream",
        json={"message": "Which professors work on ML?"},
    ) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]

    assert events[-1]["finish_reason"] == "completed"
    assert any(event.get("delta") == "Li Xin works on machine learning." for event in events)


def test_question_answer_log_admin_endpoint_requires_basic_auth(tmp_path) -> None:
    app = create_app()
    app.state.settings.admin_username = "admin"
    app.state.settings.admin_password = SecretStr("secret")
    app.state.question_answer_log = QuestionAnswerLog(tmp_path / "qa.sqlite3")
    app.state.question_answer_log.record_run(
        thread_id="thread-1",
        run_id="run-1",
        question="Who works on robotics?",
        answer="Professor A works on robotics.",
        status="completed",
        created_at="2026-04-28T01:00:00+00:00",
        finished_at="2026-04-28T01:00:03+00:00",
    )
    client = TestClient(app)

    assert client.get("/api/admin/question-answer-log").status_code == 401
    assert client.get("/api/admin/question-answer-log", auth=("admin", "wrong")).status_code == 401

    response = client.get("/api/admin/question-answer-log", auth=("admin", "secret"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["total"] == 1
    assert payload["stats"]["completed"] == 1
    assert payload["entries"][0]["question"] == "Who works on robotics?"
    assert payload["entries"][0]["answer"] == "Professor A works on robotics."


def test_question_answer_log_admin_endpoint_returns_503_when_admin_is_unconfigured(tmp_path) -> None:
    app = create_app()
    app.state.settings.admin_username = None
    app.state.settings.admin_password = None
    app.state.question_answer_log = QuestionAnswerLog(tmp_path / "qa.sqlite3")
    client = TestClient(app)

    response = client.get("/api/admin/question-answer-log", auth=("admin", "secret"))

    assert response.status_code == 503
    assert response.json()["detail"] == "Admin credentials are not configured."
