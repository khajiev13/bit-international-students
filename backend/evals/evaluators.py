from __future__ import annotations

import re
from typing import Any


_URL_RE = re.compile(r"https?://[^\s)>\]}\"']+")


def expected_professors_mentioned(*, outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    answer = _answer_text(outputs)
    missing = [
        professor["name"]
        for professor in reference_outputs.get("expected_professors", [])
        if professor["name"].casefold() not in answer
        and professor["profile_id"].replace("/", " ").replace("-", " ").casefold() not in answer
    ]
    return _score("expected_professors_mentioned", missing)


def expected_departments_mentioned(*, outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    answer = _answer_text(outputs)
    missing = []
    for department_slug in reference_outputs.get("expected_departments", []):
        department_name = department_slug.replace("-", " ")
        if department_slug.casefold() not in answer and department_name.casefold() not in answer:
            missing.append(department_slug)
    return _score("expected_departments_mentioned", missing)


def required_terms_present(*, outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    answer = _answer_text(outputs)
    missing = [term for term in reference_outputs.get("must_include_terms", []) if term.casefold() not in answer]
    return _score("required_terms_present", missing)


def forbidden_terms_absent(*, outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    answer = _answer_text(outputs)
    present = [term for term in reference_outputs.get("must_not_include_terms", []) if term.casefold() in answer]
    return _score("forbidden_terms_absent", present, failure_label="present")


def invented_urls_absent(*, outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    allowed_urls = {
        professor["detail_url"].rstrip("/")
        for professor in reference_outputs.get("expected_professors", [])
        if professor.get("detail_url")
    }
    answer_urls = {_normalize_url(match.group(0)) for match in _URL_RE.finditer(outputs.get("answer", ""))}
    unexpected_urls = sorted(answer_urls - allowed_urls)
    return _score("invented_urls_absent", unexpected_urls, failure_label="unexpected_urls")


def _answer_text(outputs: dict[str, Any]) -> str:
    return str(outputs.get("answer", "")).casefold()


def _normalize_url(url: str) -> str:
    return url.rstrip(".,;:!?").rstrip("/")


def _score(key: str, failures: list[str], *, failure_label: str = "missing") -> dict[str, Any]:
    result: dict[str, Any] = {"key": key, "score": 0 if failures else 1}
    if failures:
        result["comment"] = f"{failure_label}: {', '.join(failures)}"
    return result
