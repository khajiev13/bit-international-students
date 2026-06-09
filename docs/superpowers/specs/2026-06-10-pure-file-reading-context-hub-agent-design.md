# Pure File-Reading Context Hub Agent Design

## Summary

Convert the BIT Professor Agent runtime from a mixed custom-tool and filesystem agent into a pure file-reading DeepAgents agent. The student-facing agent should inspect `/professors` Markdown files directly, use optional `/wiki` Context Hub files for curated app/context guidance, and expose only the minimal built-in read/planning tools needed for that workflow.

The REST API can keep using `ProfessorCorpus` for `/api/departments`, `/api/professors`, and readiness counts. This migration only removes the custom professor tools from the LLM-visible agent surface.

## Goals

- Remove custom professor tools from the DeepAgents agent:
  - `list_departments`
  - `read_department_index`
  - `list_professors`
  - `search_professors`
  - `read_professor_profile`
  - `compare_professors`
- Remove LLM-visible write tools:
  - `write_file`
  - `edit_file`
- Keep only these visible agent tools:
  - `write_todos`
  - `ls`
  - `read_file`
  - `glob`
  - `grep`
- Keep `/professors` local, repo-versioned, read-only, and authoritative.
- Add `/wiki` as an optional read-only Context Hub backend route when configured.
- Keep DeepAgents internal `StateBackend` as the default backend for internal state and large-result pointers.
- Update prompt/tests so answers are grounded in Markdown file reads, not parsed cached profile objects.

## Non-Goals

- Do not remove `ProfessorCorpus` from non-agent REST API endpoints in this migration.
- Do not upload professor dossiers into Context Hub.
- Do not expose shell execution, code interpreter tools, subagent `task`, delete tools, upload routes, crawler routes, or professor-editing routes.
- Do not make `/wiki` writable from the public app.
- Do not add a public admin UI.

## Current State

The current app passes `ProfessorToolFactory(self._corpus).build()` to `create_deep_agent`. DeepAgents then injects built-in tools, and `AllowListedToolsMiddleware` filters the final set against `SAFE_TOOL_NAMES`.

That currently leaves both custom professor tools and built-in filesystem tools visible. The system prompt also names both filesystem paths and custom tools as valid routing options, which creates duplicated context and makes the agent less pure.

The previous Context Hub design exists in `docs/superpowers/specs/2026-06-08-deepagents-context-hub-production-design.md`, but `/wiki` is not implemented in local code yet.

## Target Architecture

```text
Student question
  -> FastAPI streaming endpoint
  -> ProfessorAgentService
  -> DeepAgents graph
  -> built-in read/planning tools only
  -> CompositeBackend routes:
       /professors/  local FilesystemBackend, read-only
       /wiki/        ContextHubBackend, read-only, optional
       default       StateBackend
  -> streamed Markdown answer
```

The backend route model should be:

```text
/professors/          -> FilesystemBackend(root_dir=backend/app/corpus/professors, virtual_mode=True)
/wiki/                -> ContextHubBackend(settings.context_hub_identifier), only when enabled and configured
default               -> StateBackend()
checkpointer          -> InMemorySaver()
```

`/scratch` should be removed from the public agent backend and prompt. The visible tool surface no longer includes `write_file` or `edit_file`, so a writable scratch route is unnecessary for student chat.

## Settings

Add settings:

```env
LAB4_CONTEXT_HUB_ENABLED=false
LAB4_CONTEXT_HUB_IDENTIFIER=-/bit-professor-agent
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=bit_agent_app
LAB4_DEPLOYMENT_ENV=production
```

`context_hub_configured` is true only when Context Hub is enabled, an identifier is present, and `LANGSMITH_API_KEY` is non-empty.

Readiness should report configuration booleans without making a network call:

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

## Prompt Rules

The prompt should be generated from settings so it names `/wiki` only when Context Hub is configured.

Core rules:

- `/professors` is the authoritative read-only evidence source.
- `/wiki` is curated Context Hub guidance and migration/app context, not source evidence for professor facts.
- If `/wiki` conflicts with `/professors`, trust `/professors` and mention the mismatch when relevant.
- Start broad questions at `/professors/index.md`.
- Then read `/professors/<department>/index.md`.
- For publication questions, read `/professors/<department>/publications-index.md`.
- Before recommending, comparing, or summarizing named professor candidates, read `/professors/<department>/<professor>.md`.
- Use `glob` and `grep` to discover candidate files when indexes are not enough.
- Use `write_todos` for complex planning only.
- Do not claim access to tools outside the safe list.

## Tool Surface

`SAFE_TOOL_NAMES` should become:

```python
SAFE_TOOL_NAMES = frozenset(
    {
        "write_todos",
        "ls",
        "read_file",
        "glob",
        "grep",
    }
)
```

`ProfessorToolFactory` should no longer be used by `ProfessorAgentService._build_agent`. It may be deleted if no tests or non-agent code import it. `ProfessorCorpus` remains for REST endpoints.

`SAFE_ACTIVITY_BY_TOOL` should only expose sanitized activities for the kept tools.

DeepAgents `task` prompt/tool leakage should be removed through the supported DeepAgents harness-profile configuration after upgrading:

```python
from deepagents import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile

register_harness_profile(
    "openai",
    HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)),
)
```

The exact registration key should match the provider/model resolution used by `ChatOpenAI` in this app. The final request-capture test should prove `task` is absent from both visible tools and prompt text.

## Permissions

Permissions are first-match-wins, so the allow rules must precede deny-all rules.

When Context Hub is disabled:

```text
allow read: /, /professors, /professors/**, /large_tool_results, /large_tool_results/**, /conversation_history, /conversation_history/**
deny write: /professors, /professors/**
deny read/write: /**, /**/.*
```

When Context Hub is enabled and configured, also allow:

```text
allow read: /wiki, /wiki/**
deny write: /wiki, /wiki/**
```

The default `StateBackend` can still hold DeepAgents internal large tool results and conversation-history pointers. Those should remain readable because DeepAgents may replace oversized results with file pointers that the agent must inspect with `read_file`.

## Dependencies

The current local dependency is `deepagents==0.5.3`. Official DeepAgents customization docs list `ContextHubBackend` as a backend and show:

```python
from deepagents.backends import ContextHubBackend
```

This migration should upgrade to the current compatible DeepAgents/LangChain package line from the prior Context Hub design:

```text
deepagents==0.6.8
langchain==1.3.4
langchain-core>=1.4.0
langchain-openai==1.2.2
langgraph==1.2.4
langsmith>=0.8.3
```

If the package resolver selects newer compatible transitive versions, keep the lockfile consistent and verify behavior through tests.

Official DeepAgents subagent docs also state that disabling the default general-purpose subagent requires `GeneralPurposeSubagentProfile(enabled=False)` on the active harness profile and no synchronous `subagents=`. This should be used instead of hiding `task` only through the allowlist.

## Testing Strategy

Backend tests should prove:

- Final visible tool names are exactly `write_todos`, `ls`, `read_file`, `glob`, and `grep`.
- Custom professor tools are absent from the visible agent tool set.
- `write_file`, `edit_file`, `execute`, and `task` are absent from the visible agent tool set.
- The final system prompt does not mention removed custom tools or `/scratch`.
- The prompt includes `/wiki` only when Context Hub is configured.
- `/professors` is readable through the backend.
- `/wiki` is mounted only when Context Hub is configured.
- `/professors` and `/wiki` are not writable through permissions.
- Host paths and hidden-file escape paths are denied.
- REST API endpoints that use `ProfessorCorpus` still return existing department/professor data.
- The streaming activity events remain sanitized and do not leak raw tool inputs.

## Risks And Mitigations

- **ContextHubBackend API mismatch:** Verify against installed package files after dependency upgrade and keep implementation behind a configuration gate.
- **DeepAgents prompt leakage for `task`:** Add a final request capture test proving the visible tool set and prompt do not expose removed tools where possible. If upstream still injects `task` instructions despite filtering, document and mitigate with explicit app prompt rules.
- **Loss of search shortcut quality:** The agent can use `grep` and department/publication indexes. Keep indexes as routing maps and require dossier reads before claims.
- **Large result pointers:** Keep default `StateBackend` readable for DeepAgents internal paths so context engineering still works.
- **Conversation history pointers:** Keep `/conversation_history` readable for the same DeepAgents internal pointer workflow while still hiding write tools.
- **REST regression:** Do not remove `ProfessorCorpus` or REST routes in this task.

## Acceptance Criteria

- The backend dependency set supports `ContextHubBackend`.
- The app can start with Context Hub disabled.
- The agent backend exposes `/professors` read-only.
- The agent backend exposes `/wiki` read-only when configured.
- The final visible agent tools are only `write_todos`, `ls`, `read_file`, `glob`, and `grep`.
- The app prompt instructs direct file reading and no longer recommends custom professor tools.
- Existing REST professor APIs continue to pass tests.
- Backend tests pass.
