from __future__ import annotations


SAFE_TOOL_NAMES = frozenset(
    {
        "write_todos",
        "ls",
        "read_file",
        "glob",
        "grep",
    }
)
