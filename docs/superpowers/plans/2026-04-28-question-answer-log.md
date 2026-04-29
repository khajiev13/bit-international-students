# Question Answer Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist each professor-agent question and final answer without slowing the chat stream, then expose the log through a Basic-Auth-protected admin API.

**Architecture:** Add a focused SQLite-backed `QuestionAnswerLog` store with one insert per finished run. `ProfessorAgentService` accumulates the assistant response in memory, then schedules a background write with `asyncio.to_thread` after success, configuration error, or runtime error. Docker Compose mounts a dedicated analytics volume because the backend container is read-only by default.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, SQLite from the Python standard library, pytest, Docker Compose.

---

## File Structure

- Create `backend/app/question_answer_log.py`: SQLite schema, synchronous insert/query methods, and summary counts.
- Modify `backend/app/config.py`: add `LAB4_QA_LOG_DB_PATH`, `LAB4_ADMIN_USERNAME`, and `LAB4_ADMIN_PASSWORD` settings.
- Modify `backend/app/main.py`: create one `QuestionAnswerLog` instance and attach it to `app.state`.
- Modify `backend/app/agent.py`: collect final answer text and schedule non-blocking background inserts.
- Modify `backend/app/schemas.py`: add response models for admin log output.
- Modify `backend/app/api.py`: add Basic Auth helper and `GET /api/admin/question-answer-log`.
- Create `backend/tests/test_question_answer_log.py`: direct storage tests.
- Modify `backend/tests/test_api.py`: integration tests for async run logging and admin authentication.
- Modify `docker-compose.yml`: mount a dedicated analytics volume into the backend container.
- Modify `README.md`: document the new Q&A log volume and admin credentials.

The current checkout is not a git repository, so commit steps are written as checkpoint notes. If this plan is executed inside a git checkout, make the listed commits.

---

### Task 1: SQLite Q&A Log Storage

**Files:**
- Create: `backend/tests/test_question_answer_log.py`
- Create: `backend/app/question_answer_log.py`

- [ ] **Step 1: Write failing storage tests**

Create `backend/tests/test_question_answer_log.py`:

```python
from app.question_answer_log import QuestionAnswerLog


def test_question_answer_log_records_completed_run(tmp_path):
    log = QuestionAnswerLog(tmp_path / "qa.sqlite3")

    log.record_run(
        thread_id="thread-1",
        run_id="run-1",
        question="Which professors work on robotics?",
        answer="Professor A and Professor B work on robotics.",
        status="completed",
        created_at="2026-04-28T01:00:00+00:00",
        finished_at="2026-04-28T01:00:03+00:00",
    )

    rows = log.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0]["thread_id"] == "thread-1"
    assert rows[0]["run_id"] == "run-1"
    assert rows[0]["question"] == "Which professors work on robotics?"
    assert rows[0]["answer"] == "Professor A and Professor B work on robotics."
    assert rows[0]["status"] == "completed"
    assert rows[0]["created_at"] == "2026-04-28T01:00:00+00:00"
    assert rows[0]["finished_at"] == "2026-04-28T01:00:03+00:00"


def test_question_answer_log_summary_counts_statuses(tmp_path):
    log = QuestionAnswerLog(tmp_path / "qa.sqlite3")

    for run_id, status in [
        ("run-1", "completed"),
        ("run-2", "error"),
        ("run-3", "configuration_error"),
    ]:
        log.record_run(
            thread_id="thread-1",
            run_id=run_id,
            question=f"Question {run_id}",
            answer=f"Answer {run_id}",
            status=status,
            created_at="2026-04-28T01:00:00+00:00",
            finished_at="2026-04-28T01:00:03+00:00",
        )

    assert log.summary() == {
        "total": 3,
        "completed": 1,
        "error": 1,
        "configuration_error": 1,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_question_answer_log.py -v
```

Expected: failure with `ModuleNotFoundError: No module named 'app.question_answer_log'`.

- [ ] **Step 3: Implement the storage module**

Create `backend/app/question_answer_log.py`:

```python
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class QuestionAnswerLog:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._ensure_schema()

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
        created = created_at or _utc_now()
        finished = finished_at or _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO question_answer_runs (
                    thread_id,
                    run_id,
                    question,
                    answer,
                    status,
                    created_at,
                    finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (thread_id, run_id, question, answer, status, created, finished),
            )

    def list_recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, thread_id, run_id, question, answer, status, created_at, finished_at
                FROM question_answer_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def summary(self) -> dict[str, int]:
        counts = {
            "total": 0,
            "completed": 0,
            "error": 0,
            "configuration_error": 0,
        }
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM question_answer_runs
                GROUP BY status
                """
            ).fetchall()
        for row in rows:
            status = row["status"]
            count = int(row["count"])
            counts["total"] += count
            if status in counts:
                counts[status] = count
        return counts

    def _ensure_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS question_answer_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    run_id TEXT NOT NULL UNIQUE,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_question_answer_runs_created_at
                ON question_answer_runs(created_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_question_answer_runs_status
                ON question_answer_runs(status)
                """
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
```

- [ ] **Step 4: Run storage tests**

Run:

```bash
cd backend
python -m pytest tests/test_question_answer_log.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Checkpoint**

Current checkout has no `.git` directory. If using a git checkout, commit:

```bash
git add backend/app/question_answer_log.py backend/tests/test_question_answer_log.py
git commit -m "feat: add question answer log storage"
```

---

### Task 2: Asynchronous Logging Around Agent Runs

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/agent.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Add failing integration tests**

In `backend/tests/test_api.py`, add imports:

```python
import time
```

```python
from app.question_answer_log import QuestionAnswerLog
```

Append this helper:

```python
def wait_for_log_rows(log: QuestionAnswerLog, expected_count: int, *, timeout_seconds: float = 2.0):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        rows = log.list_recent(limit=10)
        if len(rows) >= expected_count:
            return rows
        time.sleep(0.01)
    return log.list_recent(limit=10)
```

Then add:

```python
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
```

- [ ] **Step 2: Run integration tests to verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_api.py::test_stream_records_completed_question_answer_asynchronously tests/test_api.py::test_stream_records_configuration_error_question_answer_asynchronously tests/test_api.py::test_stream_continues_when_async_question_answer_log_write_fails -v
```

Expected: failures because `ProfessorAgentService` does not accept or schedule `_question_answer_log`.

- [ ] **Step 3: Add settings and app wiring**

In `backend/app/config.py`, add this field to `Settings`:

```python
    qa_log_db_path: Path = Field(
        default_factory=lambda: BACKEND_ROOT / "analytics" / "question_answer_log.sqlite3",
        validation_alias="LAB4_QA_LOG_DB_PATH",
    )
```

In `backend/app/main.py`, import the log service:

```python
from app.question_answer_log import QuestionAnswerLog
```

Then update `create_app()`:

```python
def create_app() -> FastAPI:
    settings = get_settings()
    corpus = ProfessorCorpus(settings.corpus_dir)
    question_answer_log = QuestionAnswerLog(settings.qa_log_db_path)
    agent_service = ProfessorAgentService(
        settings=settings,
        corpus=corpus,
        question_answer_log=question_answer_log,
    )

    app = FastAPI(title=settings.app_name)
    app.state.settings = settings
    app.state.corpus = corpus
    app.state.question_answer_log = question_answer_log
    app.state.agent_service = agent_service
```

Keep the existing middleware and router setup below these assignments.

- [ ] **Step 4: Add non-blocking agent logging integration**

In `backend/app/agent.py`, add imports:

```python
import logging
from datetime import UTC, datetime
```

```python
from app.question_answer_log import QuestionAnswerLog
```

Add a module logger after `SAFE_ACTIVITY_BY_TOOL`:

```python
logger = logging.getLogger(__name__)
```

Update the service constructor:

```python
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
```

Update `stream_run()` to schedule exactly one background write per run:

```python
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
```

Add this helper inside `ProfessorAgentService`:

```python
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
```

Add these module-level helpers:

```python
def _log_background_question_answer_error(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except Exception:
        logger.exception("Failed to write question-answer log row.")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
```

- [ ] **Step 5: Run integration tests**

Run:

```bash
cd backend
python -m pytest tests/test_api.py::test_stream_records_completed_question_answer_asynchronously tests/test_api.py::test_stream_records_configuration_error_question_answer_asynchronously tests/test_api.py::test_stream_continues_when_async_question_answer_log_write_fails -v
```

Expected: all three tests pass.

- [ ] **Step 6: Checkpoint**

Current checkout has no `.git` directory. If using a git checkout, commit:

```bash
git add backend/app/config.py backend/app/main.py backend/app/agent.py backend/tests/test_api.py
git commit -m "feat: record question answer logs asynchronously"
```

---

### Task 3: Admin Basic Auth and Log Endpoint

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Add failing admin API tests**

Append to `backend/tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_api.py::test_question_answer_log_admin_endpoint_requires_basic_auth tests/test_api.py::test_question_answer_log_admin_endpoint_returns_503_when_admin_is_unconfigured -v
```

Expected: failures because settings and endpoint do not exist.

- [ ] **Step 3: Add admin settings**

In `backend/app/config.py`, add these fields to `Settings`:

```python
    admin_username: str | None = Field(default=None, validation_alias="LAB4_ADMIN_USERNAME")
    admin_password: SecretStr | None = Field(default=None, validation_alias="LAB4_ADMIN_PASSWORD")
```

Add this property to `Settings`:

```python
    @property
    def admin_configured(self) -> bool:
        return bool(
            self.admin_username
            and self.admin_username.strip()
            and self.admin_password
            and self.admin_password.get_secret_value().strip()
        )
```

- [ ] **Step 4: Add admin response schemas**

In `backend/app/schemas.py`, add:

```python
class QuestionAnswerLogEntry(BaseModel):
    id: int
    thread_id: str
    run_id: str
    question: str
    answer: str
    status: str
    created_at: str
    finished_at: str


class QuestionAnswerLogStats(BaseModel):
    total: int
    completed: int
    error: int
    configuration_error: int


class QuestionAnswerLogResponse(BaseModel):
    stats: QuestionAnswerLogStats
    entries: list[QuestionAnswerLogEntry]
```

- [ ] **Step 5: Add Basic Auth helper and endpoint**

In `backend/app/api.py`, add imports:

```python
import secrets
from typing import Annotated
```

```python
from fastapi import Depends, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
```

Add schemas to the existing schema imports:

```python
    QuestionAnswerLogResponse,
```

Add a module-level security helper:

```python
security = HTTPBasic(auto_error=False)
```

Add this helper before `create_router()`:

```python
def require_admin(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
) -> None:
    settings = request.app.state.settings
    if not settings.admin_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin credentials are not configured.",
        )
    if credentials is None:
        raise _admin_auth_error()

    expected_username = settings.admin_username or ""
    expected_password = settings.admin_password.get_secret_value() if settings.admin_password else ""
    username_matches = secrets.compare_digest(credentials.username, expected_username)
    password_matches = secrets.compare_digest(credentials.password, expected_password)
    if not (username_matches and password_matches):
        raise _admin_auth_error()


def _admin_auth_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin credentials are required.",
        headers={"WWW-Authenticate": "Basic"},
    )
```

Add the route inside `create_router()`:

```python
    @router.get("/api/admin/question-answer-log", response_model=QuestionAnswerLogResponse)
    def get_question_answer_log(
        request: Request,
        _: Annotated[None, Depends(require_admin)],
        limit: int = Query(default=50, ge=1, le=500),
    ) -> QuestionAnswerLogResponse:
        return QuestionAnswerLogResponse(
            stats=request.app.state.question_answer_log.summary(),
            entries=request.app.state.question_answer_log.list_recent(limit=limit),
        )
```

- [ ] **Step 6: Run admin API tests**

Run:

```bash
cd backend
python -m pytest tests/test_api.py::test_question_answer_log_admin_endpoint_requires_basic_auth tests/test_api.py::test_question_answer_log_admin_endpoint_returns_503_when_admin_is_unconfigured -v
```

Expected: both tests pass.

- [ ] **Step 7: Checkpoint**

Current checkout has no `.git` directory. If using a git checkout, commit:

```bash
git add backend/app/config.py backend/app/schemas.py backend/app/api.py backend/tests/test_api.py
git commit -m "feat: expose authenticated question answer log"
```

---

### Task 4: Docker and Documentation

**Files:**
- Modify: `docker-compose.yml`
- Modify: `README.md`

- [ ] **Step 1: Update Docker Compose analytics volume**

In `docker-compose.yml`, update the backend service:

```yaml
    environment:
      LAB4_QA_LOG_DB_PATH: /app/analytics/question_answer_log.sqlite3
    volumes:
      - lab4_professor_scratch:/app/scratch
      - lab4_professor_analytics:/app/analytics
```

At the bottom, update volumes:

```yaml
volumes:
  lab4_professor_scratch:
  lab4_professor_analytics:
  caddy_data:
  caddy_config:
```

- [ ] **Step 2: Document admin credentials and log storage**

Add this section to `README.md` after the Cloudflare Tunnel section:

```markdown
## Question Answer Log

The backend stores each raw student question and final agent answer in SQLite. The chat stream schedules the database write in the background after each run, so students do not wait on log I/O.

In Docker Compose, the database lives on the `lab4_professor_analytics` named volume at:

```text
/app/analytics/question_answer_log.sqlite3
```

Set admin credentials in `.env` before using admin endpoints:

```env
LAB4_ADMIN_USERNAME=admin
LAB4_ADMIN_PASSWORD=replace-with-a-strong-password
```

Read recent Q&A rows:

```bash
curl -u "$LAB4_ADMIN_USERNAME:$LAB4_ADMIN_PASSWORD" \
  "http://127.0.0.1:8081/api/admin/question-answer-log?limit=50"
```
```

- [ ] **Step 3: Run focused backend tests**

Run:

```bash
cd backend
python -m pytest tests/test_question_answer_log.py tests/test_api.py -v
```

Expected: all backend tests pass.

- [ ] **Step 4: Validate Docker Compose config**

Run:

```bash
docker compose config
```

Expected: config renders successfully and backend has both `/app/scratch` and `/app/analytics` volume mounts.

- [ ] **Step 5: Checkpoint**

Current checkout has no `.git` directory. If using a git checkout, commit:

```bash
git add docker-compose.yml README.md
git commit -m "chore: persist question answer log volume"
```

---

### Task 5: Final Verification

**Files:**
- Verify all modified files from previous tasks.

- [ ] **Step 1: Run all backend tests**

Run:

```bash
cd backend
python -m pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
cd frontend
npm test -- --run
```

Expected: all frontend tests pass. No frontend behavior changed, so failures here indicate an integration or environment issue to inspect before delivery.

- [ ] **Step 3: Optional local smoke test**

Run:

```bash
docker compose up --build
```

In another terminal:

```bash
curl http://127.0.0.1:8081/healthz
curl -u "$LAB4_ADMIN_USERNAME:$LAB4_ADMIN_PASSWORD" \
  "http://127.0.0.1:8081/api/admin/question-answer-log?limit=5"
```

Expected: health check returns `ok`; admin endpoint returns JSON with `stats` and `entries`.

- [ ] **Step 4: Final checkpoint**

Current checkout has no `.git` directory. If using a git checkout, commit:

```bash
git status --short
git log --oneline -5
```

Expected: either all previous commits exist or the working tree contains only the planned files.
