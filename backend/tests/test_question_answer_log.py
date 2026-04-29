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
