# Question Answer Log Design

## Context

The BIT Professor Agent currently streams one response at a time through the FastAPI backend and keeps the visible chat history in the browser. The backend has in-memory session tracking, but it does not persist questions, answers, or usage statistics after a container restart.

The goal is to add a simple operational log of what students ask and what the agent answers. This is intentionally not a full analytics system.

## Scope

The first version stores one row per finished agent run:

- `id`
- `thread_id`
- `run_id`
- `question`
- `answer`
- `created_at`
- `finished_at`
- `status`

The log stores raw question text and the final assistant response. It does not redact content, store tool activity, store IP addresses, store user agents, create user accounts, or identify individual students.

## Architecture

Add a small backend analytics module backed by SQLite. The database file lives on a dedicated writable Docker volume, separate from the existing DeepAgents scratch volume.

Suggested runtime path:

```text
/app/analytics/question_answer_log.sqlite3
```

The backend settings expose this path through an environment variable with a sensible default. During local tests, the path can point at a temporary file.

## Data Flow

When a stream run starts, the backend keeps the `thread_id`, `run_id`, `question`, and start timestamp in memory. It does not write to SQLite at run start.

As response deltas stream from the agent, the service accumulates the final assistant text in memory for that run. It still streams deltas to the frontend exactly as it does today.

When the run finishes successfully, the backend schedules a background write with the final `answer`, `created_at`, `finished_at`, and `status = "completed"`. The stream must not wait for SQLite before sending the user their response.

If the model is not configured or the run fails, the backend schedules a background write with the question and the user-facing error/configuration message as the answer, then marks the row as `error` or `configuration_error`.

The background write can use `asyncio.to_thread` or an equivalent background task wrapper around the synchronous SQLite store. There is no need for the agent stream to wait for analytics I/O.

## Admin Access

The initial implementation can focus on storage and tests. A follow-up endpoint can expose recent Q&A logs and simple counts behind admin authentication, for example:

```text
GET /api/admin/question-answer-log
```

Admin authentication should use credentials configured through environment variables rather than hard-coded values:

- `LAB4_ADMIN_USERNAME`
- `LAB4_ADMIN_PASSWORD`

For the first admin API, HTTP Basic authentication is enough. The backend compares the supplied username and password with the configured values using constant-time comparison, and returns `401 Unauthorized` when credentials are missing or wrong. This works well for a small private admin surface and does not require a database-backed user system.

The endpoint is not required for the first storage pass unless we decide we want immediate in-browser viewing. If we later build an admin web page, it can either keep using Basic Auth or move to a small login form with a secure session cookie.

## Failure Handling

Analytics logging must not break chat or slow down streaming. If the SQLite database cannot be opened or a background write fails, the backend logs the failure server-side. Users should still receive the answer when the model succeeds.

## Testing

Backend tests should cover:

- a successful streamed run eventually creates one completed Q&A row from a background write
- an error run records the question and user-facing error response
- configuration errors are recorded
- analytics write failures do not break the streaming response
- existing stream behavior and history handling remain unchanged

## Deployment

Docker Compose adds a new named volume for analytics data and mounts it into the backend container at `/app/analytics`. Because the backend container is read-only by default, this writable mount is required for SQLite persistence.

The new volume is separate from `lab4_professor_scratch` so clearing agent scratch files does not erase the Q&A log by accident.
