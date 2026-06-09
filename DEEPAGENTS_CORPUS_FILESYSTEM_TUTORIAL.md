# DeepAgents Pure File-Reading Corpus Guide

This note explains the public Professor Agent file model after the pure file-reading migration.

Useful references:

- DeepAgents backends: https://docs.langchain.com/oss/python/deepagents/backends
- DeepAgents permissions: https://docs.langchain.com/oss/python/deepagents/permissions
- DeepAgents subagents: https://docs.langchain.com/oss/python/deepagents/subagents
- DeepAgents profiles: https://docs.langchain.com/oss/python/deepagents/profiles

The core rule is simple:

- `/professors` is the local read-only source of truth.
- `/wiki` is optional read-only Context Hub guidance.
- `write_todos` is planning state, not a Markdown-file mutation.
- The public agent should only see `write_todos`, `ls`, `read_file`, `glob`, and `grep`.

## What The Agent Reads

The professor source files live in the repository under:

```text
backend/app/corpus/professors
```

The agent sees that folder as:

```text
/professors
```

Important files:

- `/professors/index.md` routes broad questions to likely departments.
- `/professors/<department>/index.md` gives a department roster and topic guide.
- `/professors/<department>/publications-index.md` routes paper and publication questions.
- `/professors/<department>/<professor>.md` is the final evidence layer for summaries, comparisons, and publication claims.

Indexes are routing maps. Individual professor dossiers are the final evidence source.

## Optional Context Hub

When these settings are configured, the app mounts a LangSmith Context Hub repository at `/wiki`:

```env
LAB4_CONTEXT_HUB_ENABLED=true
LAB4_CONTEXT_HUB_IDENTIFIER=-/bit-professor-agent
LANGSMITH_API_KEY=...
```

Use `/wiki` for application guidance, migration notes, and operating context. Do not use it as professor-fact evidence. If `/wiki` conflicts with `/professors`, trust `/professors`.

The readiness endpoint reports Context Hub and LangSmith status as booleans:

```json
{
  "context_hub_enabled": true,
  "context_hub_configured": true,
  "langsmith_tracing_configured": true
}
```

## Backend Shape

The public agent uses a composite backend:

```python
CompositeBackend(
    default=StateBackend(),
    routes={
        "/professors/": FilesystemBackend(root_dir=profiles_dir, virtual_mode=True),
        "/wiki/": ContextHubBackend(settings.context_hub_identifier),
    },
)
```

The `/wiki/` route is only present when Context Hub is enabled and configured. The `StateBackend` default is still important because DeepAgents can put internal large-result and conversation-history pointers under its own state-backed paths.

## Permission Shape

Permission rules are first-match-wins, so hidden-file denies come before broad read allows.

Read allows:

- `/`
- `/professors`
- `/professors/**`
- `/large_tool_results`
- `/large_tool_results/**`
- `/conversation_history`
- `/conversation_history/**`
- `/wiki` and `/wiki/**` only when Context Hub is configured

Write denies:

- `/professors`
- `/professors/**`
- `/wiki`
- `/wiki/**`
- all other paths

Host paths and hidden files are denied.

## Prompt Workflow

For broad or topic-based questions, the agent should:

1. Read `/professors/index.md`.
2. Read likely department indexes.
3. Use `glob` or `grep` when indexes are not enough.
4. Read individual professor dossiers before recommending or comparing candidates.
5. Use publication indexes for paper, venue, journal, or representative-work questions.

The final answer should say what was checked when evidence is thin or incomplete.
