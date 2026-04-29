from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.corpus import ProfessorCorpus


PROFESSOR_TOOL_NAMES = frozenset(
    {
        "list_departments",
        "read_department_index",
        "list_professors",
        "search_professors",
        "read_professor_profile",
        "compare_professors",
    }
)

DEEPAGENT_WORKSPACE_TOOL_NAMES = frozenset(
    {
        "write_todos",
        "ls",
        "read_file",
        "glob",
        "grep",
        "write_file",
        "edit_file",
    }
)

SAFE_TOOL_NAMES = PROFESSOR_TOOL_NAMES | DEEPAGENT_WORKSPACE_TOOL_NAMES


class DepartmentSlugArgs(BaseModel):
    department_slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ListProfessorsArgs(BaseModel):
    department_slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SearchProfessorsArgs(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=8, ge=1, le=20)
    department_slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ReadProfessorProfileArgs(BaseModel):
    profile_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*$")


class CompareProfessorsArgs(BaseModel):
    profile_ids: list[str] = Field(min_length=2, max_length=6)


class ProfessorToolFactory:
    def __init__(self, corpus: ProfessorCorpus) -> None:
        self._corpus = corpus

    def build(self) -> list[BaseTool]:
        return [
            StructuredTool.from_function(
                name="list_departments",
                description="List BIT departments available in the read-only professor corpus.",
                func=self._list_departments,
            ),
            StructuredTool.from_function(
                name="read_department_index",
                description="Read one department index from the read-only professor corpus by department slug.",
                func=self._read_department_index,
                args_schema=DepartmentSlugArgs,
            ),
            StructuredTool.from_function(
                name="list_professors",
                description="List BIT professor profiles available in the read-only professor corpus, optionally within one department.",
                func=self._list_professors,
                args_schema=ListProfessorsArgs,
            ),
            StructuredTool.from_function(
                name="search_professors",
                description="Search the read-only BIT professor corpus by department, name, research area, title, or profile text.",
                func=self._search_professors,
                args_schema=SearchProfessorsArgs,
            ),
            StructuredTool.from_function(
                name="read_professor_profile",
                description="Read one BIT professor profile from the read-only corpus by department-qualified profile ID.",
                func=self._read_professor_profile,
                args_schema=ReadProfessorProfileArgs,
            ),
            StructuredTool.from_function(
                name="compare_professors",
                description="Compare two to six BIT professor profiles from the read-only corpus by department-qualified profile ID.",
                func=self._compare_professors,
                args_schema=CompareProfessorsArgs,
            ),
        ]

    def _list_departments(self) -> str:
        return self._json([department.model_dump() for department in self._corpus.list_departments()])

    def _read_department_index(self, department_slug: str) -> str:
        return self._json(self._corpus.get_department_index(department_slug))

    def _list_professors(self, department_slug: str | None = None) -> str:
        return self._json([summary.model_dump() for summary in self._corpus.list_professors(department_slug=department_slug)])

    def _search_professors(self, query: str, limit: int = 8, department_slug: str | None = None) -> str:
        hits = self._corpus.search(query, limit=limit, department_slug=department_slug)
        return self._json([hit.__dict__ for hit in hits])

    def _read_professor_profile(self, profile_id: str) -> str:
        profile = self._corpus.get_profile(profile_id)
        return self._json(profile.model_dump())

    def _compare_professors(self, profile_ids: list[str]) -> str:
        profiles = self._corpus.compare(profile_ids)
        comparison = [
            {
                "slug": profile.slug,
                "profile_id": profile.profile_id,
                "professor_slug": profile.professor_slug,
                "department_slug": profile.department_slug,
                "department_name": profile.department_name,
                "name": profile.name,
                "title": profile.title,
                "school": profile.school,
                "research_interests": profile.research_interests,
                "detail_url": profile.detail_url,
                "email": profile.email,
                "summary": profile.summary,
                "selected_publications": profile.sections.get("Publications", [])[:5],
            }
            for profile in profiles
        ]
        return self._json(comparison)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
