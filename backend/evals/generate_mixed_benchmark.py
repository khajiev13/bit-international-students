from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.corpus import DepartmentNotFoundError, ProfessorCorpus, ProfessorNotFoundError


DEFAULT_OUTPUT_PATH = BACKEND_DIR / "evals" / "datasets" / "professor_agent_mixed_v1.jsonl"
CORPUS_DIR = BACKEND_DIR / "app" / "corpus"


@dataclass(frozen=True)
class ExampleSpec:
    id: str
    category: str
    difficulty: str
    question: str
    expected_professor_ids: list[str] = field(default_factory=list)
    expected_departments: list[str] = field(default_factory=list)
    evidence_files: list[str] = field(default_factory=list)
    must_include_terms: list[str] = field(default_factory=list)
    must_not_include_terms: list[str] = field(default_factory=list)


EXAMPLE_SPECS = [
    ExampleSpec(
        id="profile-cs-li-xin",
        category="single_professor_profile",
        difficulty="easy",
        question="Tell me about LI Xin's research profile in Computer Science and Technology.",
        expected_professor_ids=["computer-science-and-technology/li-xin"],
        expected_departments=["computer-science-and-technology"],
        must_include_terms=["Machine Learning", "Deep Reinforcement Learning", "robotics"],
    ),
    ExampleSpec(
        id="profile-law-yang-kuan",
        category="single_professor_profile",
        difficulty="easy",
        question="What does YANG Kuan in the Law school work on?",
        expected_professor_ids=["law/yang-kuan"],
        expected_departments=["law"],
        must_include_terms=["International Space Law", "Air and Space Law"],
    ),
    ExampleSpec(
        id="profile-education-zhang-lishan",
        category="single_professor_profile",
        difficulty="easy",
        question="Summarize Zhang Lishan's profile for a student interested in intelligent tutoring.",
        expected_professor_ids=["education/zhang-lishan"],
        expected_departments=["education"],
        must_include_terms=["intelligent tutoring", "learning analytics"],
    ),
    ExampleSpec(
        id="topic-natural-language-processing",
        category="topic_advisor_matching",
        difficulty="medium",
        question="Who should I look at for natural language processing or machine translation?",
        expected_professor_ids=["computer-science-and-technology/huang-heyan"],
        expected_departments=["computer-science-and-technology"],
        must_include_terms=["Natural Language Processing", "Machine Translation"],
    ),
    ExampleSpec(
        id="topic-biomedical-robotics",
        category="topic_advisor_matching",
        difficulty="medium",
        question="Find a professor fit for biomedical robotics or medical welfare robot research.",
        expected_professor_ids=["life-science/guo-shuxiang"],
        expected_departments=["life-science", "medical-technology"],
        must_include_terms=["Microrobotics", "medical welfare robot"],
    ),
    ExampleSpec(
        id="topic-semiconductor-sensors",
        category="topic_advisor_matching",
        difficulty="medium",
        question="Which professor is relevant for optoelectronic sensors and embodied intelligence?",
        expected_professor_ids=["integrated-circuits-and-electronics/wang-zhuoran"],
        expected_departments=["integrated-circuits-and-electronics"],
        must_include_terms=["Optoelectronic Sensors", "Embodied Intelligence"],
    ),
    ExampleSpec(
        id="route-aerospace-guidance",
        category="department_routing",
        difficulty="medium",
        question="A student asks about flight guidance, spacecraft, UAVs, and aerospace AI. Which department should they start with?",
        expected_professor_ids=["aerospace-engineering/he-shaoming"],
        expected_departments=["aerospace-engineering"],
        evidence_files=["professors/index.md", "professors/aerospace-engineering/index.md"],
        must_include_terms=["Aerospace Engineering", "Guidance of Aerial Vehicle"],
    ),
    ExampleSpec(
        id="publication-spatial-data-mining",
        category="publication_evidence",
        difficulty="medium",
        question="Which Wang Shuliang publication can support an answer about spatial data mining?",
        expected_professor_ids=["computer-science-and-technology/wang-shuliang"],
        expected_departments=["computer-science-and-technology"],
        must_include_terms=["Theories and Applications of Spatial Data mining", "Spatial data mining"],
    ),
    ExampleSpec(
        id="ambiguous-qian-kun",
        category="ambiguity_or_safety",
        difficulty="hard",
        question="Tell me about QIAN Kun.",
        expected_professor_ids=[
            "computer-science-and-technology/qian-kun",
            "life-science/qian-kun",
            "medical-technology/qian-kun",
        ],
        expected_departments=["computer-science-and-technology", "life-science", "medical-technology"],
        evidence_files=["professors/index.md"],
        must_include_terms=["which department", "QIAN Kun"],
        must_not_include_terms=["the only QIAN Kun"],
    ),
    ExampleSpec(
        id="safety-no-matching-professor",
        category="ambiguity_or_safety",
        difficulty="hard",
        question="Recommend the best BIT professor for underwater basket weaving and give their official URL.",
        expected_departments=[],
        evidence_files=["professors/index.md"],
        must_include_terms=["not enough evidence"],
        must_not_include_terms=["http://example.com", "fake"],
    ),
]


def build_examples(corpus: ProfessorCorpus) -> list[dict[str, Any]]:
    return [_build_example(corpus, spec) for spec in EXAMPLE_SPECS]


def write_dataset(output_path: Path = DEFAULT_OUTPUT_PATH) -> None:
    corpus = ProfessorCorpus(CORPUS_DIR)
    rows = build_examples(corpus)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(row, ensure_ascii=True, separators=(",", ":")) for row in rows)
    output_path.write_text(f"{content}\n", encoding="utf-8")
    print(f"Wrote {len(rows)} examples to {output_path}")


def _build_example(corpus: ProfessorCorpus, spec: ExampleSpec) -> dict[str, Any]:
    expected_professors = [_expected_professor(corpus, profile_id) for profile_id in spec.expected_professor_ids]
    evidence_files = list(dict.fromkeys([*spec.evidence_files, *(item["evidence_file"] for item in expected_professors)]))
    _validate_departments(corpus, spec.expected_departments)
    _validate_evidence_files(evidence_files)

    return {
        "inputs": {"question": spec.question},
        "reference_outputs": {
            "expected_professors": expected_professors,
            "expected_departments": spec.expected_departments,
            "must_include_terms": spec.must_include_terms,
            "must_not_include_terms": spec.must_not_include_terms,
            "evidence_files": evidence_files,
        },
        "metadata": {
            "id": spec.id,
            "category": spec.category,
            "difficulty": spec.difficulty,
        },
    }


def _expected_professor(corpus: ProfessorCorpus, profile_id: str) -> dict[str, str]:
    try:
        profile = corpus.get_profile(profile_id)
    except ProfessorNotFoundError as exc:
        raise RuntimeError(f"Missing expected professor profile: {profile_id}") from exc
    return {
        "profile_id": profile.profile_id,
        "name": profile.name,
        "detail_url": profile.detail_url or "",
        "evidence_file": f"professors/{profile.profile_id}.md",
    }


def _validate_departments(corpus: ProfessorCorpus, department_slugs: list[str]) -> None:
    known_departments = {department.slug for department in corpus.list_departments()}
    missing = sorted(set(department_slugs) - known_departments)
    if missing:
        raise RuntimeError(f"Missing expected department(s): {', '.join(missing)}")


def _validate_evidence_files(evidence_files: list[str]) -> None:
    for evidence_file in evidence_files:
        evidence_path = (CORPUS_DIR / evidence_file).resolve()
        if CORPUS_DIR.resolve() not in evidence_path.parents:
            raise RuntimeError(f"Evidence file escapes corpus directory: {evidence_file}")
        if not evidence_path.is_file():
            raise RuntimeError(f"Missing evidence file: {evidence_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the professor-agent mixed eval benchmark.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="JSONL output path. Defaults to the committed dataset path.",
    )
    args = parser.parse_args()
    try:
        write_dataset(args.output)
    except (DepartmentNotFoundError, ProfessorNotFoundError, RuntimeError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()
