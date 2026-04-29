from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
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
    return datetime.now(timezone.utc).isoformat()
