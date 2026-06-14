import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from app.corpus import ProfessorCorpus


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = BACKEND_DIR / "evals" / "datasets" / "professor_agent_mixed_v1.jsonl"
GENERATOR_PATH = BACKEND_DIR / "evals" / "generate_mixed_benchmark.py"
CORPUS_DIR = BACKEND_DIR / "app" / "corpus"


def _load_dataset() -> list[dict[str, object]]:
    assert DATASET_PATH.is_file(), f"Missing eval dataset: {DATASET_PATH}"
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(DATASET_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        assert line.strip(), f"Blank JSONL line at {line_number}"
        rows.append(json.loads(line))
    return rows


def test_mixed_benchmark_dataset_contract() -> None:
    rows = _load_dataset()
    corpus = ProfessorCorpus(CORPUS_DIR)

    assert len(rows) == 10
    assert Counter(row["metadata"]["category"] for row in rows) == {
        "single_professor_profile": 3,
        "topic_advisor_matching": 3,
        "department_routing": 1,
        "publication_evidence": 1,
        "ambiguity_or_safety": 2,
    }

    seen_ids: set[str] = set()
    for row in rows:
        assert sorted(row) == ["inputs", "metadata", "reference_outputs"]
        assert isinstance(row["inputs"]["question"], str)
        assert row["inputs"]["question"].strip()
        assert row["metadata"]["difficulty"] in {"easy", "medium", "hard"}

        reference_outputs = row["reference_outputs"]
        assert "evidence_files" in reference_outputs
        assert "must_include_terms" in reference_outputs
        assert "must_not_include_terms" in reference_outputs

        example_id = row["metadata"]["id"]
        assert example_id not in seen_ids
        seen_ids.add(example_id)

        for evidence_file in reference_outputs["evidence_files"]:
            evidence_path = (CORPUS_DIR / evidence_file).resolve()
            assert CORPUS_DIR.resolve() in evidence_path.parents
            assert evidence_path.is_file(), evidence_file

        for professor in reference_outputs.get("expected_professors", []):
            profile = corpus.get_profile(professor["profile_id"])
            assert professor["name"] == profile.name
            assert professor["evidence_file"] in reference_outputs["evidence_files"]
            if profile.detail_url:
                assert professor["detail_url"] == profile.detail_url

        for department_slug in reference_outputs.get("expected_departments", []):
            assert any(department.slug == department_slug for department in corpus.list_departments())


def test_mixed_benchmark_generator_recreates_dataset(tmp_path: Path) -> None:
    assert GENERATOR_PATH.is_file(), f"Missing eval generator: {GENERATOR_PATH}"
    generated_path = tmp_path / "generated.jsonl"

    result = subprocess.run(
        [sys.executable, str(GENERATOR_PATH), "--output", str(generated_path)],
        cwd=BACKEND_DIR,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Wrote 10 examples" in result.stdout
    assert generated_path.read_text(encoding="utf-8") == DATASET_PATH.read_text(encoding="utf-8")
