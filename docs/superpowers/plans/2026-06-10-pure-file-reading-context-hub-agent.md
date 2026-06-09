# Pure File-Reading Context Hub Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the public LLM agent's custom professor tools and visible write tools with a pure file-reading DeepAgents workflow over `/professors`, plus an optional read-only `/wiki` Context Hub route.

**Architecture:** FastAPI and REST endpoints continue to use `ProfessorCorpus`; `ProfessorAgentService` builds a DeepAgents graph with only built-in planning/read tools visible, a `CompositeBackend` routing `/professors/` to a virtual local `FilesystemBackend`, `/wiki/` to `ContextHubBackend` when configured, and all internal DeepAgents pointers to `StateBackend`.

**Tech Stack:** Python 3.11, FastAPI, Pydantic Settings, DeepAgents 0.6.x, LangChain 1.3.x, LangGraph, LangSmith Context Hub, pytest, uv.

---

## Documentation Checked

- Official DeepAgents Backends: `ContextHubBackend`, `CompositeBackend`, `FilesystemBackend(virtual_mode=True)`, and internal `/large_tool_results/` plus `/conversation_history/` paths.
- Official DeepAgents Permissions: ordered `FilesystemPermission` rules are first-match-wins and default-permissive when no rule matches.
- Official DeepAgents Subagents and Profiles: disable the default `task` tool with `GeneralPurposeSubagentProfile(enabled=False)` on the active harness profile and pass no synchronous `subagents=`.

## File Map

- `backend/pyproject.toml`, `backend/uv.lock`: dependency upgrade and lock consistency.
- `backend/app/config.py`: Context Hub, LangSmith, and deployment settings.
- `backend/app/schemas.py`: readiness response fields.
- `backend/app/api.py`: readiness response population.
- `backend/app/agent.py`: agent construction, backend routing, permissions, visible tool activity labels.
- `backend/app/prompts.py`: settings-aware file-reading prompt.
- `backend/app/tools.py`: safe tool constants; remove or stop exposing custom professor tool factory.
- `backend/tests/test_security.py`: tool surface, prompt, permission, backend, and final request-capture tests.
- `backend/tests/test_api.py`: readiness and sanitized activity expectations.
- `.env.example`, `README.md`: configuration docs for Context Hub and LangSmith.

## Implementation Steps

- [x] Task 1: Add failing settings and readiness tests.
  - Update `backend/tests/test_api.py` so `/readyz` expects `context_hub_enabled`, `context_hub_configured`, and `langsmith_tracing_configured`.
  - Add direct `Settings` assertions for enabled/unconfigured and enabled/configured Context Hub cases if needed.
  - Run the focused tests and confirm they fail because fields/properties do not exist yet.

- [x] Task 2: Add configuration and readiness implementation.
  - Add `context_hub_enabled`, `context_hub_identifier`, `langsmith_tracing`, `langsmith_endpoint`, `langsmith_api_key`, `langsmith_project`, and `deployment_env` to `Settings`.
  - Add computed properties:
    - `context_hub_configured`: enabled, identifier non-empty, LangSmith API key non-empty.
    - `langsmith_tracing_configured`: tracing enabled and LangSmith API key non-empty.
  - Extend `ReadyResponse` and `/readyz`.
  - Re-run focused readiness tests.

- [x] Task 3: Upgrade DeepAgents dependency line.
  - Update `backend/pyproject.toml` to the compatible DeepAgents/LangChain line that provides `ContextHubBackend`, harness profiles, and `GeneralPurposeSubagentProfile`.
  - Run `uv lock` or `uv sync --extra test`.
  - Add/import-check test coverage or run an explicit import command for:
    - `from deepagents.backends import ContextHubBackend`
    - `from deepagents import HarnessProfile, GeneralPurposeSubagentProfile, register_harness_profile`

- [x] Task 4: Add failing pure-tool-surface and backend tests.
  - In `backend/tests/test_security.py`, change the safe tool test to expect exactly:
    - `write_todos`
    - `ls`
    - `read_file`
    - `glob`
    - `grep`
  - Assert removed custom tools, `write_file`, `edit_file`, `execute`, and `task` are absent from the filtered visible tool set.
  - Update permissions tests:
    - allow reads for `/`, `/professors/**`, `/large_tool_results/**`, `/conversation_history/**`.
    - deny writes to `/professors/**`, `/wiki/**`, and all other paths.
    - deny host-path and hidden-file escape reads.
  - Update backend tests:
    - `/professors/index.md` reads from local corpus.
    - `/scratch` is not mounted.
    - `/wiki` is absent when not configured and present when configured; use monkeypatching if needed to avoid network calls while proving route construction.
  - Add a final request-capture test that builds the agent with a fake chat model or capture middleware and proves visible tools/prompt do not include the removed tool names or `/scratch`.
  - Run focused security tests and confirm expected failures.

- [x] Task 5: Implement pure agent construction.
  - Stop passing `ProfessorToolFactory(...).build()` to `create_deep_agent`; pass no custom professor tools.
  - Keep `SAFE_TOOL_NAMES = frozenset({"write_todos", "ls", "read_file", "glob", "grep"})`.
  - Reduce `SAFE_ACTIVITY_BY_TOOL` to those tool names only.
  - Remove `scratch_dir` from `_build_agent_backend`.
  - Build `CompositeBackend(default=StateBackend(), routes={"/professors/": FilesystemBackend(..., virtual_mode=True)})`.
  - Add `/wiki/`: `ContextHubBackend(settings.context_hub_identifier)` only when `settings.context_hub_configured`.
  - Register a harness profile for the active model/provider to disable the general-purpose subagent and exclude `write_file`, `edit_file`, `execute`, and `task` as a second belt-and-suspenders guard.
  - Update permissions with explicit allow rules followed by deny rules.
  - Re-run focused security tests.

- [x] Task 6: Rewrite prompt around direct file reads.
  - Replace `DEEP_AGENT_SYSTEM_PROMPT` with a builder that can include `/wiki` guidance only when configured.
  - Remove references to custom professor tools, `/scratch`, `write_file`, `edit_file`, and subagent `task`.
  - Add explicit file-reading workflow for root index, department index, publication index, and individual dossiers.
  - Re-run prompt/security tests.

- [x] Task 7: Update stream tests and sanitization.
  - Update fake agent emitted events so it includes kept tools and removed-tool negative events.
  - Expected public activity labels should only include kept tools.
  - Assert raw tool input, `execute`, custom professor tool names, `write_file`, and `/Users/private` are absent from serialized stream output.
  - Re-run `backend/tests/test_api.py` focused tests.

- [x] Task 8: Update docs and examples.
  - Update `.env.example` with Context Hub and LangSmith environment variables.
  - Update `README.md` with the new pure file-reading agent architecture and optional `/wiki` Context Hub route.
  - Remove or avoid claiming a writable scratch route for the public agent.

- [x] Task 9: Full verification and review.
  - Run `uv run python -m pytest -q` from `backend`.
  - Run targeted import/agent-construction verification for Context Hub-disabled mode.
  - Review `git diff` for accidental unrelated changes.
  - Use superpowers:requesting-code-review or a verification sub-agent for a final risk pass if time permits.

## Acceptance Criteria

- `/readyz` reports Context Hub and LangSmith configuration booleans without exposing secrets.
- `ContextHubBackend` imports from the installed dependency set.
- The agent backend reads `/professors` locally and optionally mounts `/wiki`.
- `/scratch` is not in the public agent backend, permissions, or prompt.
- Final visible tools are exactly `write_todos`, `ls`, `read_file`, `glob`, and `grep`.
- Removed custom professor tools and write/shell/subagent tools are absent from final visible tools and prompt.
- REST professor API tests still pass.
- All backend tests pass.
