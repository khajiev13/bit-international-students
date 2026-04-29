from pathlib import Path

import pytest

from app.corpus import DepartmentNotFoundError, ProfessorCorpus, ProfessorNotFoundError


def test_department_grouped_corpus_counts_and_profile_ids() -> None:
    corpus = ProfessorCorpus(Path("app/corpus"))

    departments = corpus.list_departments()
    professors = corpus.list_professors()

    assert corpus.department_count == 22
    assert len(departments) == 22
    assert corpus.count == 753
    assert len(professors) == 753
    assert any(professor.slug == "computer-science-and-technology/li-xin" for professor in professors)
    assert all(not professor.slug.endswith("/publications-index") for professor in professors)

    profile = corpus.get_profile("computer-science-and-technology/li-xin")
    assert profile.name == "LI Xin"
    assert profile.profile_id == "computer-science-and-technology/li-xin"
    assert profile.professor_slug == "li-xin"
    assert profile.department_slug == "computer-science-and-technology"
    assert profile.department_name == "Computer Science and Technology"
    assert profile.detail_url == "https://isc.bit.edu.cn/schools/csat/knowingprofessors5/b186322.htm"
    assert "Machine Learning" in profile.research_interests

    summary = next(professor for professor in professors if professor.slug == "computer-science-and-technology/li-xin")
    assert summary.detail_url == profile.detail_url


def test_department_listing_and_index_reads() -> None:
    corpus = ProfessorCorpus(Path("app/corpus"))

    computer_science = next(
        department for department in corpus.list_departments() if department.slug == "computer-science-and-technology"
    )
    assert computer_science.professor_count == 60
    assert computer_science.index_path == "professors/computer-science-and-technology/index.md"

    index = corpus.get_department_index("computer-science-and-technology")
    assert index["department"]["slug"] == "computer-science-and-technology"
    assert "# Computer Science and Technology Professor Index" in index["content"]
    assert len(corpus.list_professors("computer-science-and-technology")) == 60


def test_bare_and_repeated_slugs_are_rejected() -> None:
    corpus = ProfessorCorpus(Path("app/corpus"))

    with pytest.raises(ProfessorNotFoundError):
        corpus.get_profile("li-xin")
    with pytest.raises(ProfessorNotFoundError):
        corpus.get_profile("qian-kun")

    hits = corpus.search("QIAN Kun", limit=10)
    qian_hits = {hit.profile_id for hit in hits}
    expected_qian_hits = {
        "computer-science-and-technology/qian-kun",
        "life-science/qian-kun",
        "medical-technology/qian-kun",
    }
    assert expected_qian_hits <= qian_hits
    assert all(hit.detail_url for hit in hits if hit.profile_id in expected_qian_hits)


def test_slug_traversal_is_rejected() -> None:
    corpus = ProfessorCorpus(Path("app/corpus"))

    with pytest.raises(ProfessorNotFoundError):
        corpus.get_profile("../professors")
    with pytest.raises(ProfessorNotFoundError):
        corpus.get_profile("computer-science-and-technology/li-xin/../../pyproject")
    with pytest.raises(DepartmentNotFoundError):
        corpus.get_department_index("../professors")
