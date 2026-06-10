import ast
from fnmatch import fnmatchcase
from pathlib import Path

from pydantic import SecretStr

from app.agent import (
    AllowListedToolsMiddleware,
    FixedSystemPromptMiddleware,
    _build_agent_backend,
    _filesystem_permissions,
    _register_pure_file_reading_harness_profile,
)
from app.config import Settings
from app.corpus import ProfessorCorpus
from app.prompts import DEEP_AGENT_SYSTEM_PROMPT, build_deep_agent_system_prompt
from app.tools import SAFE_TOOL_NAMES


BACKEND_ROOT = Path(__file__).resolve().parents[1]
VISIBLE_AGENT_TOOLS = {"write_todos", "ls", "read_file", "glob", "grep"}
REMOVED_AGENT_TOOLS = {
    "list_departments",
    "read_department_index",
    "list_professors",
    "search_professors",
    "read_professor_profile",
    "compare_professors",
    "write_file",
    "edit_file",
    "execute",
    "task",
    "delete_file",
}


def _check_fs_permission(rules, operation: str, path: str) -> str:
    for rule in rules:
        if operation in rule.operations and any(fnmatchcase(path, pattern) for pattern in rule.paths):
            return rule.mode
    return "allow"


def test_agent_allowlist_is_pure_file_reading_surface() -> None:
    assert SAFE_TOOL_NAMES == VISIBLE_AGENT_TOOLS
    assert not (SAFE_TOOL_NAMES & REMOVED_AGENT_TOOLS)
    assert isinstance(AllowListedToolsMiddleware(SAFE_TOOL_NAMES), AllowListedToolsMiddleware)


def test_allowlist_middleware_filters_to_file_reading_tools() -> None:
    class DummyRequest:
        def __init__(self, tools) -> None:
            self.tools = tools

        def override(self, *, tools):
            return DummyRequest(tools)

    middleware = AllowListedToolsMiddleware(SAFE_TOOL_NAMES)
    request = DummyRequest(
        [
            {"name": "list_professors"},
            {"name": "ls"},
            {"name": "execute"},
            {"name": "write_file"},
            {"name": "edit_file"},
            {"name": "read_file"},
            {"name": "glob"},
            {"name": "grep"},
            {"name": "write_todos"},
            {"name": "read_professor_profile"},
            {"name": "task"},
        ]
    )

    filtered_tools = middleware.wrap_model_call(request, lambda filtered_request: filtered_request.tools)

    assert [tool["name"] for tool in filtered_tools] == [
        "ls",
        "read_file",
        "glob",
        "grep",
        "write_todos",
    ]


def test_backend_source_does_not_import_shell_backends_or_define_mutating_routes() -> None:
    forbidden_imports = {"LocalShellBackend", "LangSmithSandbox"}
    forbidden_route_terms = {"upload", "crawl", "add-professor", "add_professor"}

    for source_path in (BACKEND_ROOT / "app").glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported_names = {
            alias.name.rsplit(".", maxsplit=1)[-1]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert not (imported_names & forbidden_imports), source_path

        source_text = source_path.read_text(encoding="utf-8")
        if source_path.name == "api.py":
            assert not any(term in source_text for term in forbidden_route_terms), source_path


def test_deepagents_filesystem_permissions_are_first_match_safe() -> None:
    rules = _filesystem_permissions()

    assert _check_fs_permission(rules, "read", "/") == "allow"
    assert _check_fs_permission(rules, "read", "/professors/index.md") == "allow"
    assert _check_fs_permission(rules, "read", "/large_tool_results/result-1.md") == "allow"
    assert _check_fs_permission(rules, "read", "/conversation_history/thread-1.md") == "allow"
    assert _check_fs_permission(rules, "read", "/scratch/search-notes.md") == "deny"
    assert _check_fs_permission(rules, "write", "/scratch/search-notes.md") == "deny"
    assert _check_fs_permission(rules, "write", "/professors/computer-science-and-technology/li-xin.md") == "deny"
    assert _check_fs_permission(rules, "read", "/Users/private/.env") == "deny"
    assert _check_fs_permission(rules, "read", "/professors/.env") == "deny"
    assert _check_fs_permission(rules, "write", "/tmp/escape.md") == "deny"


def test_deepagents_filesystem_permissions_allow_read_only_wiki_when_configured() -> None:
    rules = _filesystem_permissions(context_hub_configured=True)

    assert _check_fs_permission(rules, "read", "/wiki/index.md") == "allow"
    assert _check_fs_permission(rules, "write", "/wiki/index.md") == "deny"


def test_composite_backend_routes_corpus_read_without_scratch() -> None:
    corpus = ProfessorCorpus(Path("app/corpus"))
    backend = _build_agent_backend(
        profiles_dir=corpus.profiles_dir,
        settings=Settings(_env_file=None),
    )

    corpus_read = backend.read("/professors/index.md")
    assert corpus_read.error is None
    assert corpus_read.file_data is not None
    assert "BIT Professor Corpus Index" in corpus_read.file_data["content"]
    assert "/professors/" in backend.routes
    assert "/scratch/" not in backend.routes
    assert "/wiki/" not in backend.routes


def test_composite_backend_routes_context_hub_when_configured(monkeypatch) -> None:
    class FakeContextHubBackend:
        def __init__(self, identifier: str, *, client) -> None:
            self.identifier = identifier
            self.client = client

    monkeypatch.setattr("app.agent.ContextHubBackend", FakeContextHubBackend)
    corpus = ProfessorCorpus(Path("app/corpus"))
    backend = _build_agent_backend(
        profiles_dir=corpus.profiles_dir,
        settings=Settings(
            _env_file=None,
            context_hub_enabled=True,
            context_hub_identifier="-/bit-professor-agent",
            langsmith_api_key=SecretStr("test-langsmith-key"),
        ),
    )

    assert "/wiki/" in backend.routes
    assert backend.routes["/wiki/"].identifier == "-/bit-professor-agent"
    assert backend.routes["/wiki/"].client.api_url == "https://api.smith.langchain.com"


def test_system_prompt_owns_scope_and_read_only_policy() -> None:
    prompt = DEEP_AGENT_SYSTEM_PROMPT

    assert prompt.startswith("# BIT Professor Agent")
    assert "## Routing Workflow" in prompt
    assert "## Evidence Depth" in prompt
    assert "## Publication Questions" in prompt
    assert "## Professor URLs" in prompt
    assert "## Filesystem Rules" in prompt
    assert "BIT Professor Agent" in prompt
    assert "Lab 4" not in prompt
    assert "read-only" in prompt
    assert "/professors/index.md" in prompt
    assert "/scratch" not in prompt
    assert "write_todos" in prompt
    assert "detail_url" in prompt
    assert "Do not invent URLs" in prompt
    assert "read only enough dossiers to verify a concise shortlist" in prompt
    assert "inspect the dossiers for the candidates you actively recommend" in prompt
    assert "/professors/<department>/publications-index.md" in prompt
    assert "publication-related questions" in prompt
    assert "verify the `## Publications` section" in prompt
    assert "Always return the final answer as Markdown" in prompt
    assert "Markdown bullets" in prompt
    assert "non-judgmental" in prompt
    assert "possible fits" in prompt
    assert "Do not criticize professors" in prompt
    assert "compare evidence neutrally" in prompt
    assert "unrelated requests" in prompt
    assert "Shell execution" not in prompt
    for removed_tool in REMOVED_AGENT_TOOLS:
        assert removed_tool not in prompt


def test_system_prompt_bounds_broad_file_reading_workflows() -> None:
    prompt = DEEP_AGENT_SYSTEM_PROMPT

    assert "default to a shortlist of 3 to 5 professor candidates" in prompt
    assert "Do not attempt an exhaustive corpus review unless the student explicitly asks for it" in prompt
    assert "Do not narrate tool use, planning, or progress" in prompt


def test_default_prompt_excludes_context_hub_when_unconfigured() -> None:
    assert "/wiki" not in DEEP_AGENT_SYSTEM_PROMPT


def test_prompt_includes_context_hub_only_when_configured() -> None:
    prompt = build_deep_agent_system_prompt(context_hub_configured=True)

    assert "/wiki" in prompt
    assert "Context Hub" in prompt
    assert "If `/wiki` conflicts with `/professors`, trust `/professors`" in prompt


def test_final_deepagents_request_exposes_only_file_reading_tools() -> None:
    from deepagents import FilesystemPermission, create_deep_agent
    from langchain.agents.middleware.types import AgentMiddleware
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.memory import InMemorySaver

    class CaptureModelRequestMiddleware(AgentMiddleware):
        def __init__(self) -> None:
            self.tool_names: set[str] = set()
            self.system_prompt = ""

        def wrap_model_call(self, request, handler):
            self.tool_names = {tool.name for tool in request.tools}
            self.system_prompt = request.system_prompt or ""
            return AIMessage(content="captured")

    prompt = build_deep_agent_system_prompt(context_hub_configured=False)
    _register_pure_file_reading_harness_profile(
        base_system_prompt=prompt,
        key="fakelistchatmodel",
    )
    capture = CaptureModelRequestMiddleware()
    corpus = ProfessorCorpus(Path("app/corpus"))
    agent = create_deep_agent(
        model=FakeListChatModel(responses=["unused"]),
        tools=[],
        system_prompt=None,
        middleware=[
            AllowListedToolsMiddleware(SAFE_TOOL_NAMES),
            FixedSystemPromptMiddleware(prompt),
            capture,
        ],
        subagents=[],
        permissions=_filesystem_permissions(FilesystemPermission),
        backend=_build_agent_backend(profiles_dir=corpus.profiles_dir, settings=Settings(_env_file=None)),
        checkpointer=InMemorySaver(),
    )

    agent.invoke(
        {"messages": [{"role": "user", "content": "Which professors work on machine learning?"}]},
        config={"configurable": {"thread_id": "tool-surface-test"}},
    )

    assert capture.tool_names == VISIBLE_AGENT_TOOLS
    assert not (capture.tool_names & REMOVED_AGENT_TOOLS)
    assert "/scratch" not in capture.system_prompt
    for removed_tool in REMOVED_AGENT_TOOLS:
        assert removed_tool not in capture.system_prompt
