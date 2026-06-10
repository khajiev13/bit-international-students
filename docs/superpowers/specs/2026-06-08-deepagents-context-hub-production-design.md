# DeepAgents Context Hub Production Design

## Summary

Upgrade the BIT Professor Agent production backend to the current DeepAgents 0.6 line while keeping the existing FastAPI, Docker Compose, Caddy, and Cloudflare deployment model. Add LangSmith Context Hub as an optional curated `/wiki` backend next to the existing read-only `/professors` corpus and writable `/scratch` workspace. Move production observability and admin-style run inspection to LangSmith traces instead of the custom local Q&A log.

The first production release keeps the current student-facing behavior stable. It does not upload the full professor corpus to Context Hub, does not expose shell execution, does not enable code interpreter tools, and does not move runtime execution to LangSmith Managed Deep Agents.

## Current State

- The public app serves student chat through React, FastAPI streaming, Caddy, Docker Compose, and an optional Cloudflare tunnel.
- The backend is pinned to `deepagents==0.5.3`, `langchain==1.2.15`, `langchain-openai==1.2.1`, and `langgraph==1.1.9`.
- The agent uses `create_deep_agent` with `ChatOpenAI`, custom professor tools, `FilesystemPermission`, `CompositeBackend`, `FilesystemBackend`, `StateBackend`, and `InMemorySaver`.
- The current backend routes `/professors/` to local read-only professor Markdown, `/scratch/` to local writable notes, and default state to `StateBackend`.
- Streaming uses `agent.astream_events` with `version="v2"` and maps `on_tool_start` plus `on_chat_model_stream` into the frontend NDJSON stream.
- `backend/tests/test_security.py` imports the private helper `deepagents.middleware.permissions._check_fs_permission`.
- A custom admin Q&A log stores local SQLite entries and exposes `/api/admin/question-answer-log`.
- A private LangSmith Context Hub agent context named `bit-professor-agent` already exists with an `AGENTS.md` seed describing the multi-backend wiki model.

## Goals

- Upgrade to the latest compatible package line verified on 2026-06-08:
  - `deepagents==0.6.8`
  - `langchain==1.3.4`
  - `langchain-core>=1.4.0`
  - `langchain-openai==1.2.2`
  - `langgraph==1.2.4`
  - `langsmith>=0.8.3`
- Keep `/professors` local, repo-versioned, read-only, and authoritative.
- Add an optional `/wiki` route backed by `ContextHubBackend`.
- Preserve `/scratch` as the only writable local filesystem area.
- Move run inspection, tracing, tool-call visibility, latency/error monitoring, and production admin review into LangSmith.
- Remove the custom admin Q&A endpoint and local Q&A logging from the production path.
- Add health/readiness diagnostics that show whether Context Hub and LangSmith tracing are configured without exposing secrets.
- Keep the frontend streaming contract stable for the first production release.

## Non-Goals

- Do not move runtime execution to LangSmith Managed Deep Agents in this release.
- Do not upload all 753 professor dossiers into Context Hub in this release.
- Do not enable `CodeInterpreterMiddleware`, shell execution, crawler routes, upload routes, professor editing, or delete tools in the public app.
- Do not adopt `astream_events` with `version="v3"` in the same release unless v2 is removed or broken by the dependency upgrade.
- Do not create a new public admin UI.

## Architecture

Production continues to run the existing app:

```text
Student browser
  -> Caddy
  -> FastAPI
  -> ProfessorAgentService
  -> DeepAgents graph
  -> CompositeBackend routes
  -> streamed Markdown answer
```

The backend route model becomes:

```text
/professors/  -> FilesystemBackend(root_dir=backend/app/corpus/professors, virtual_mode=True)
/wiki/        -> ContextHubBackend(identifier=settings.context_hub_identifier)
/scratch/     -> FilesystemBackend(root_dir=settings.agent_scratch_dir, virtual_mode=True)
default       -> StateBackend()
checkpoints   -> InMemorySaver for this release
```

If Context Hub is disabled or not configured, `/wiki` is absent from the backend routes and the agent prompt tells the model that only `/professors` and `/scratch` are available. This lets local development and production fallback work without LangSmith credentials.

## Settings

Add backend settings:

```env
LAB4_CONTEXT_HUB_ENABLED=false
LAB4_CONTEXT_HUB_IDENTIFIER=-/bit-professor-agent
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=bit_agent_app
LAB4_DEPLOYMENT_ENV=production
```

`LAB4_CONTEXT_HUB_ENABLED` controls whether `/wiki` is mounted. `LAB4_CONTEXT_HUB_IDENTIFIER` is explicit because Context Hub identifiers can vary by workspace or owner. `LANGSMITH_API_KEY` is required for both LangSmith tracing and `ContextHubBackend`.

Readiness must report:

```json
{
  "status": "ready",
  "department_count": 22,
  "professor_count": 753,
  "model_configured": true,
  "context_hub_enabled": true,
  "context_hub_configured": true,
  "langsmith_tracing_configured": true
}
```

Readiness must not call LangSmith on every request. It should report configuration state, not perform a network health check.

## Prompt and Context Rules

The production prompt must preserve the current professor-corpus workflow and add the Context Hub rules from the `bit-professor-agent` AGENTS.md seed:

- `/professors` is read-only source evidence from the app repository.
- `/wiki` is curated agent wiki context and migration notes backed by Context Hub.
- `/scratch` is writable working notes only.
- Root and department indexes route discovery, but professor dossiers are final evidence.
- If `/wiki` summaries disagree with `/professors` dossiers, trust `/professors` and mention the mismatch.
- Never assume a bare professor slug is unique.
- Do not claim access to web pages or tools outside the safe tool list.
- Do not expose shell execution or code interpreter capabilities.

The prompt should be generated from settings so it only names `/wiki` as available when Context Hub is enabled and configured.

## LangSmith Observability

LangSmith becomes the production admin and observability layer. The app should emit traces to `LANGSMITH_PROJECT=bit_agent_app` and enrich agent runs with metadata:

```json
{
  "app": "bit-professor-agent",
  "deployment_env": "production",
  "thread_id": "session thread id from the FastAPI request",
  "run_id": "application run id generated by ProfessorAgentService",
  "context_hub_enabled": true,
  "context_hub_identifier": "-/bit-professor-agent",
  "deepagents_version": "0.6.8"
}
```

This replaces the local Q&A admin log for production debugging. LangSmith covers traces, runs, tool calls, errors, latency, token/cost metrics, dashboards, metadata filters, and feedback workflows. The app no longer needs `/api/admin/question-answer-log`, local admin credentials, or the SQLite Q&A volume for the upgraded production path.

The migration removes the old Q&A log from the production request path rather than keeping a second admin observability system alive.

## Security

- Keep Docker backend `read_only: true`.
- Keep `/tmp` as `tmpfs` with `noexec,nosuid`.
- Keep Linux capabilities dropped and `no-new-privileges:true`.
- Keep `/professors` read-only through both backend routing and DeepAgents permissions.
- Keep `/scratch` as the only writable route.
- Add `/wiki` read permissions when Context Hub is enabled.
- Do not add write permissions for `/wiki` in the public app.
- Do not expose `execute`, `task`, delete tools, shell backends, upload routes, crawler routes, or professor-editing routes.
- Do not log secrets in readiness, traces, or errors.

## Testing Strategy

Use test-driven development for implementation.

Backend unit tests:

- Settings parse Context Hub and LangSmith flags correctly.
- Backend routes include `/wiki/` only when Context Hub is enabled and configured.
- Backend routes keep `/professors/` and `/scratch/` behavior unchanged.
- Permissions allow reading `/professors`, `/scratch`, and optionally `/wiki`.
- Permissions deny writing `/professors`, writing `/wiki`, hidden-file escape paths, `/tmp`, and host paths.
- Security tests no longer import private DeepAgents helpers.
- Prompt generation includes `/wiki` only when enabled.
- Readiness response includes Context Hub and LangSmith configuration booleans.
- Admin Q&A endpoint is removed from the production API.

Integration checks:

- `uv run python -m pytest -v`
- Docker build for backend and frontend.
- Frontend tests and build:
  - `npm test -- --run`
  - `npm run build`
- A local smoke test verifies `/readyz`, `/api/departments`, session creation, and streaming response startup.

Manual production checks:

- Confirm LangSmith project receives traces with metadata.
- Confirm Context Hub page shows `bit-professor-agent` and current `AGENTS.md`.
- Confirm public app still answers a normal professor question.
- Confirm no public route exposes admin Q&A logs.
- Confirm `/wiki` failures degrade gracefully when disabled.

## Rollout Plan

1. Create a branch for the production migration.
2. Update dependencies and lock files.
3. Replace private DeepAgents security tests with public behavior tests.
4. Add settings and prompt generation for optional Context Hub.
5. Add `/wiki` backend routing behind `LAB4_CONTEXT_HUB_ENABLED`.
6. Add LangSmith trace metadata.
7. Remove the admin Q&A log from production.
8. Run the full backend/frontend test suite.
9. Build Docker images locally.
10. Deploy to staging or a production-like host with:
    - `LAB4_CONTEXT_HUB_ENABLED=true`
    - `LAB4_CONTEXT_HUB_IDENTIFIER=-/bit-professor-agent`
    - `LANGSMITH_TRACING=true`
    - `LANGSMITH_PROJECT=bit_agent_app`
11. Validate LangSmith traces and Context Hub access.
12. Promote Context Hub commit `13ac11f1` or a newer reviewed commit to production.
13. Deploy production.
14. Monitor LangSmith dashboards for errors, latency, tool failures, and token usage.

## Risks and Mitigations

- DeepAgents 0.6.8 raises dependency floors. Mitigation: upgrade the compatible LangChain, LangGraph, LangSmith, and provider package set together.
- Streaming v3 could change frontend behavior. Mitigation: keep v2 for the first release and make v3 a separate task.
- Context Hub network/API failures could break answers. Mitigation: mount `/wiki` only when configured; make `/professors` sufficient for normal questions.
- Context Hub curated notes could drift from corpus evidence. Mitigation: prompt and tests require `/professors` to win conflicts.
- Removing local admin logs could reduce fallback diagnostics. Mitigation: attach rich LangSmith metadata and verify traces before production cutover.
- Private DeepAgents internals may move. Mitigation: remove private helper imports from tests and test behavior through public backend APIs.

## Acceptance Criteria

- The app runs on DeepAgents 0.6.8 with the compatible LangChain/LangGraph package line.
- `/professors` remains read-only and authoritative.
- `/wiki` is mounted from Context Hub only when enabled and configured.
- `/scratch` remains writable and isolated.
- The public frontend streaming behavior remains compatible.
- LangSmith traces appear in `bit_agent_app` with `thread_id`, `run_id`, environment, Context Hub, and package metadata.
- Custom admin Q&A logging is not part of the production path.
- All backend and frontend tests pass.
- Docker build succeeds.
- Production rollout has a clear fallback: disable `LAB4_CONTEXT_HUB_ENABLED` and redeploy while preserving `/professors` behavior.
