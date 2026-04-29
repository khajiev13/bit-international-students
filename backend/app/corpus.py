from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.schemas import DepartmentSummary, ProfessorProfile, ProfessorSummary


_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PROFILE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*$")
_BULLET_RE = re.compile(r"^\s*-\s+(?P<body>.+?)\s*$")
_FIELD_RE = re.compile(r"^(?P<key>[A-Za-z][A-Za-z /&()-]*):\s*(?P<value>.+)$")
_ROUTING_ROW_RE = re.compile(
    r"^\|\s*(?P<name>[^|]+?)\s*\|\s*`(?P<slug>[a-z0-9-]+)`\s*\|\s*(?P<count>\d+)\s*\|\s*(?P<good_for>[^|]+?)\s*\|"
)
_NON_PROFILE_MARKDOWN = {"index.md", "publications-index.md"}


class ProfessorNotFoundError(LookupError):
    pass


class DepartmentNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class SearchHit:
    slug: str
    profile_id: str
    professor_slug: str
    department_slug: str
    department_name: str
    name: str
    title: str | None
    research_interests: list[str]
    detail_url: str | None
    score: int
    snippet: str


class ProfessorCorpus:
    def __init__(self, corpus_dir: Path) -> None:
        self._corpus_dir = corpus_dir.resolve()
        self._profiles_dir = (self._corpus_dir / "professors").resolve()
        self._departments = self._load_departments()
        self._profiles = self._load_profiles()
        self._summaries = [profile.to_summary() for profile in self._profiles.values()]

    @property
    def count(self) -> int:
        return len(self._profiles)

    @property
    def department_count(self) -> int:
        return len(self._departments)

    @property
    def profiles_dir(self) -> Path:
        return self._profiles_dir

    @property
    def slugs(self) -> set[str]:
        return set(self._profiles)

    @property
    def known_terms(self) -> set[str]:
        return self.known_identity_terms | self.known_research_terms

    @property
    def known_identity_terms(self) -> set[str]:
        terms: set[str] = set()
        for profile in self._profiles.values():
            terms.add(profile.name.lower())
            terms.update(alias.lower() for alias in profile.aliases)
            terms.add(profile.profile_id.replace("/", " ").replace("-", " "))
            terms.add(profile.professor_slug.replace("-", " "))
            terms.add(profile.department_slug.replace("-", " "))
            terms.add(profile.department_name.lower())
        return {term for term in terms if term}

    @property
    def known_research_terms(self) -> set[str]:
        terms: set[str] = set()
        for profile in self._profiles.values():
            terms.update(interest.lower() for interest in profile.research_interests)
        return {term for term in terms if term}

    def list_departments(self) -> list[DepartmentSummary]:
        return list(self._departments.values())

    def get_department_index(self, department_slug: str) -> dict[str, object]:
        safe_slug = self._validate_department_slug(department_slug)
        department = self._departments[safe_slug]
        index_path = self._profiles_dir / safe_slug / "index.md"
        return {
            "department": department.model_dump(),
            "content": index_path.read_text(encoding="utf-8"),
        }

    def list_professors(self, department_slug: str | None = None) -> list[ProfessorSummary]:
        if department_slug is None:
            return list(self._summaries)
        safe_slug = self._validate_department_slug(department_slug)
        return [summary for summary in self._summaries if summary.department_slug == safe_slug]

    def get_profile(self, profile_id: str) -> ProfessorProfile:
        safe_profile_id = self._validate_profile_id(profile_id)
        try:
            return self._profiles[safe_profile_id]
        except KeyError as exc:
            raise ProfessorNotFoundError(f"Professor profile not found: {safe_profile_id}") from exc

    def search(self, query: str, *, limit: int = 8, department_slug: str | None = None) -> list[SearchHit]:
        normalized_query = query.casefold().strip()
        if not normalized_query:
            return []
        safe_department_slug = self._validate_department_slug(department_slug) if department_slug else None
        query_terms = {term for term in re.split(r"[\W_]+", normalized_query) if len(term) >= 2}
        hits: list[SearchHit] = []
        for profile in self._profiles.values():
            if safe_department_slug and profile.department_slug != safe_department_slug:
                continue
            haystack = " ".join(
                [
                    profile.profile_id,
                    profile.professor_slug,
                    profile.department_slug,
                    profile.department_name,
                    profile.name,
                    " ".join(profile.aliases),
                    profile.title or "",
                    profile.school or "",
                    " ".join(profile.research_interests),
                    profile.content,
                ]
            ).casefold()
            score = sum(haystack.count(term) for term in query_terms)
            if normalized_query in haystack:
                score += 4
            if score <= 0:
                continue
            hits.append(
                SearchHit(
                    slug=profile.slug,
                    profile_id=profile.profile_id,
                    professor_slug=profile.professor_slug,
                    department_slug=profile.department_slug,
                    department_name=profile.department_name,
                    name=profile.name,
                    title=profile.title,
                    research_interests=profile.research_interests,
                    detail_url=profile.detail_url,
                    score=score,
                    snippet=self._snippet(profile.content, query_terms),
                )
            )
        hits.sort(key=lambda item: (-item.score, item.department_name, item.name, item.profile_id))
        return hits[: max(1, min(limit, 20))]

    def compare(self, profile_ids: list[str]) -> list[ProfessorProfile]:
        unique_profile_ids = list(dict.fromkeys(profile_ids))
        return [self.get_profile(profile_id) for profile_id in unique_profile_ids[:6]]

    def _load_departments(self) -> dict[str, DepartmentSummary]:
        if not self._profiles_dir.is_dir():
            msg = f"Professor corpus directory is missing: {self._profiles_dir}"
            raise RuntimeError(msg)

        routed = self._root_department_routes()
        departments: dict[str, DepartmentSummary] = {}
        for department_dir in sorted(path for path in self._profiles_dir.iterdir() if path.is_dir()):
            slug = department_dir.name
            if not _SLUG_RE.fullmatch(slug):
                continue
            index_path = department_dir / "index.md"
            if not index_path.is_file():
                continue
            content = index_path.read_text(encoding="utf-8")
            routed_department = routed.get(slug)
            department_name = routed_department.name if routed_department else self._department_name_from_index(slug, content)
            professor_count = len([path for path in department_dir.glob("*.md") if path.name not in _NON_PROFILE_MARKDOWN])
            departments[slug] = DepartmentSummary(
                slug=slug,
                name=department_name,
                professor_count=routed_department.professor_count if routed_department else professor_count,
                index_path=f"professors/{slug}/index.md",
                good_for=routed_department.good_for if routed_department else None,
            )

        if not departments:
            msg = f"No department indexes found in {self._profiles_dir}"
            raise RuntimeError(msg)
        return dict(sorted(departments.items(), key=lambda item: item[1].name))

    def _root_department_routes(self) -> dict[str, DepartmentSummary]:
        index_path = self._profiles_dir / "index.md"
        if not index_path.is_file():
            return {}
        routes: dict[str, DepartmentSummary] = {}
        for line in index_path.read_text(encoding="utf-8").splitlines():
            match = _ROUTING_ROW_RE.match(line)
            if not match:
                continue
            slug = match.group("slug")
            routes[slug] = DepartmentSummary(
                slug=slug,
                name=match.group("name").strip(),
                professor_count=int(match.group("count")),
                index_path=f"professors/{slug}/index.md",
                good_for=match.group("good_for").strip(),
            )
        return routes

    def _load_profiles(self) -> dict[str, ProfessorProfile]:
        profiles: dict[str, ProfessorProfile] = {}
        for department_slug, department in self._departments.items():
            department_dir = self._profiles_dir / department_slug
            for profile_path in sorted(department_dir.glob("*.md")):
                professor_slug = profile_path.stem
                if profile_path.name in _NON_PROFILE_MARKDOWN or not _SLUG_RE.fullmatch(professor_slug):
                    continue
                profile_id = f"{department_slug}/{professor_slug}"
                profile = self._parse_profile(profile_id, professor_slug, department, profile_path)
                profiles[profile_id] = profile
        if not profiles:
            msg = f"No professor profiles found in {self._profiles_dir}"
            raise RuntimeError(msg)
        return dict(sorted(profiles.items(), key=lambda item: (item[1].department_name, item[1].name, item[0])))

    def _validate_department_slug(self, department_slug: str) -> str:
        if not _SLUG_RE.fullmatch(department_slug):
            raise DepartmentNotFoundError("Department not found.")
        candidate = (self._profiles_dir / department_slug / "index.md").resolve()
        if self._profiles_dir not in candidate.parents:
            raise DepartmentNotFoundError("Department not found.")
        if department_slug not in self._departments:
            raise DepartmentNotFoundError(f"Department not found: {department_slug}")
        return department_slug

    def _validate_profile_id(self, profile_id: str) -> str:
        if not _PROFILE_ID_RE.fullmatch(profile_id):
            raise ProfessorNotFoundError("Professor profile not found.")
        department_slug, professor_slug = profile_id.split("/", maxsplit=1)
        try:
            self._validate_department_slug(department_slug)
        except DepartmentNotFoundError as exc:
            raise ProfessorNotFoundError("Professor profile not found.") from exc
        candidate = (self._profiles_dir / department_slug / f"{professor_slug}.md").resolve()
        if self._profiles_dir not in candidate.parents:
            raise ProfessorNotFoundError("Professor profile not found.")
        return profile_id

    def _parse_profile(
        self,
        profile_id: str,
        professor_slug: str,
        department: DepartmentSummary,
        profile_path: Path,
    ) -> ProfessorProfile:
        content = profile_path.read_text(encoding="utf-8")
        title = self._first_heading(content) or professor_slug.replace("-", " ").title()
        fields, sections = self._parse_sections(content)
        aliases = self._split_list(fields.get("aliases"))
        interests = sections.get("Research Interests", [])
        detail_url = fields.get("detail_url")
        return ProfessorProfile(
            slug=profile_id,
            profile_id=profile_id,
            professor_slug=professor_slug,
            department_slug=department.slug,
            department_name=department.name,
            name=fields.get("name") or title,
            title=fields.get("title"),
            school=fields.get("school") or department.name,
            research_interests=interests,
            summary=self._summary_from_profile(fields.get("biography"), interests),
            aliases=aliases,
            email=fields.get("email"),
            phone=fields.get("phone"),
            detail_url=detail_url,
            sections=sections,
            content=content,
        )

    def _parse_sections(self, content: str) -> tuple[dict[str, str], dict[str, list[str]]]:
        fields: dict[str, str] = {}
        sections: dict[str, list[str]] = {}
        current_section: str | None = None
        paragraph_accumulator: list[str] = []

        def flush_paragraph() -> None:
            if current_section and paragraph_accumulator:
                value = " ".join(paragraph_accumulator).strip()
                if value:
                    sections.setdefault(current_section, []).append(value)
                paragraph_accumulator.clear()

        for line in content.splitlines():
            if line.startswith("## "):
                flush_paragraph()
                current_section = line[3:].strip()
                sections.setdefault(current_section, [])
                continue
            bullet_match = _BULLET_RE.match(line)
            if bullet_match and current_section:
                flush_paragraph()
                body = bullet_match.group("body").strip()
                field_match = _FIELD_RE.match(body)
                if field_match and current_section == "Basic Information":
                    fields[field_match.group("key").lower().replace(" ", "_")] = field_match.group("value").strip()
                else:
                    sections.setdefault(current_section, []).append(body)
                continue
            if current_section and line.strip() and not line.startswith("#"):
                paragraph_accumulator.append(line.strip())
            elif not line.strip():
                flush_paragraph()
        flush_paragraph()
        if "Biography" in sections and sections["Biography"]:
            fields["biography"] = sections["Biography"][0]
        detail_url = self._detail_url(content)
        if detail_url:
            fields["detail_url"] = detail_url
        return fields, sections

    @staticmethod
    def _department_name_from_index(slug: str, content: str) -> str:
        for line in content.splitlines():
            if line.startswith("- school:"):
                return line.split(":", 1)[1].strip()
        for line in content.splitlines():
            if line.startswith("# "):
                heading = line[2:].strip()
                return heading.removesuffix(" Professor Index").strip()
        return slug.replace("-", " ").title()

    @staticmethod
    def _first_heading(content: str) -> str | None:
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return None

    @staticmethod
    def _detail_url(content: str) -> str | None:
        for line in content.splitlines():
            if line.startswith("- detail_url:"):
                return line.split(":", 1)[1].strip()
        return None

    @staticmethod
    def _split_list(value: str | None) -> list[str]:
        if not value:
            return []
        return [part.strip() for part in value.split(",") if part.strip()]

    @staticmethod
    def _summary_from_profile(biography: str | None, interests: list[str]) -> str | None:
        if biography:
            return biography[:280].rstrip()
        if interests:
            return ", ".join(interests[:4])
        return None

    @staticmethod
    def _snippet(content: str, query_terms: set[str]) -> str:
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
        for line in lines:
            folded = line.casefold()
            if any(term in folded for term in query_terms):
                return line[:260]
        return lines[0][:260] if lines else ""
