import ast
from pathlib import Path

from deepagents.middleware.permissions import _check_fs_permission

from app.agent import AllowListedToolsMiddleware, _build_agent_backend, _filesystem_permissions
from app.corpus import ProfessorCorpus
from app.prompts import DEEP_AGENT_SYSTEM_PROMPT
from app.tools import PROFESSOR_TOOL_NAMES, SAFE_TOOL_NAMES, ProfessorToolFactory


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DANGEROUS_TOOL_NAMES = {"execute", "task", "delete_file"}


def test_custom_tool_allowlist_contains_no_dangerous_tools() -> None:
    corpus = ProfessorCorpus(Path("app/corpus"))

    tools = ProfessorToolFactory(corpus).build()
    tool_names = {tool.name for tool in tools}

    assert tool_names == PROFESSOR_TOOL_NAMES
    assert not (tool_names & DANGEROUS_TOOL_NAMES)
    assert {"write_todos", "write_file", "edit_file"} <= SAFE_TOOL_NAMES
    assert isinstance(AllowListedToolsMiddleware(SAFE_TOOL_NAMES), AllowListedToolsMiddleware)


def test_allowlist_middleware_filters_default_deepagent_tools() -> None:
    class DummyRequest:
        def __init__(self, tools) -> None:
            self.tools = tools

        def override(self, *, tools):
            return DummyRequest(tools)

    middleware = AllowListedToolsMiddleware(SAFE_TOOL_NAMES)
    request = DummyRequest(
        [
            {"name": "list_professors"},
            {"name": "execute"},
            {"name": "write_file"},
            {"name": "edit_file"},
            {"name": "read_file"},
            {"name": "write_todos"},
            {"name": "read_professor_profile"},
            {"name": "task"},
        ]
    )

    filtered_tools = middleware.wrap_model_call(request, lambda filtered_request: filtered_request.tools)

    assert [tool["name"] for tool in filtered_tools] == [
        "list_professors",
        "write_file",
        "edit_file",
        "read_file",
        "write_todos",
        "read_professor_profile",
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
    assert _check_fs_permission(rules, "read", "/scratch/search-notes.md") == "allow"
    assert _check_fs_permission(rules, "write", "/scratch/search-notes.md") == "allow"
    assert _check_fs_permission(rules, "write", "/professors/computer-science-and-technology/li-xin.md") == "deny"
    assert _check_fs_permission(rules, "read", "/Users/private/.env") == "deny"
    assert _check_fs_permission(rules, "write", "/tmp/escape.md") == "deny"


def test_composite_backend_routes_corpus_read_and_scratch_write(tmp_path: Path) -> None:
    corpus = ProfessorCorpus(Path("app/corpus"))
    backend = _build_agent_backend(profiles_dir=corpus.profiles_dir, scratch_dir=tmp_path / "scratch")

    corpus_read = backend.read("/professors/index.md")
    assert corpus_read.error is None
    assert corpus_read.file_data is not None
    assert "BIT Professor Corpus Index" in corpus_read.file_data["content"]

    scratch_write = backend.write("/scratch/search-notes.md", "first note")
    assert scratch_write.error is None
    assert (tmp_path / "scratch" / "search-notes.md").read_text(encoding="utf-8") == "first note"

    scratch_edit = backend.edit("/scratch/search-notes.md", "first", "updated")
    assert scratch_edit.error is None
    assert (tmp_path / "scratch" / "search-notes.md").read_text(encoding="utf-8") == "updated note"


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
    assert "/scratch" in prompt
    assert "write_todos" in prompt
    assert "detail_url" in prompt
    assert "Do not invent URLs" in prompt
    assert "read every professor Markdown file that is needed" in prompt
    assert "inspect each candidate's dossier" in prompt
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
    assert "Shell execution" in prompt


def test_tool_descriptions_do_not_expose_teaching_lab_framing() -> None:
    corpus = ProfessorCorpus(Path("app/corpus"))
    tool_descriptions = "\n".join(tool.description or "" for tool in ProfessorToolFactory(corpus).build())

    assert "Lab 4" not in tool_descriptions
    assert "lab 4" not in tool_descriptions.lower()
