from evals.evaluators import (
    expected_departments_mentioned,
    expected_professors_mentioned,
    forbidden_terms_absent,
    invented_urls_absent,
    required_terms_present,
)


REFERENCE_OUTPUTS = {
    "expected_professors": [
        {
            "profile_id": "computer-science-and-technology/li-xin",
            "name": "LI Xin",
            "detail_url": "https://isc.bit.edu.cn/schools/csat/knowingprofessors5/b186322.htm",
            "evidence_file": "professors/computer-science-and-technology/li-xin.md",
        }
    ],
    "expected_departments": ["computer-science-and-technology"],
    "must_include_terms": ["Machine Learning", "Deep Reinforcement Learning"],
    "must_not_include_terms": ["the only LI Xin"],
    "evidence_files": ["professors/computer-science-and-technology/li-xin.md"],
}


def test_code_evaluators_pass_grounded_answer() -> None:
    outputs = {
        "answer": (
            "LI Xin in Computer Science and Technology works on Machine Learning and "
            "Deep Reinforcement Learning. Official URL: "
            "https://isc.bit.edu.cn/schools/csat/knowingprofessors5/b186322.htm"
        )
    }

    assert expected_professors_mentioned(outputs=outputs, reference_outputs=REFERENCE_OUTPUTS)["score"] == 1
    assert expected_departments_mentioned(outputs=outputs, reference_outputs=REFERENCE_OUTPUTS)["score"] == 1
    assert required_terms_present(outputs=outputs, reference_outputs=REFERENCE_OUTPUTS)["score"] == 1
    assert forbidden_terms_absent(outputs=outputs, reference_outputs=REFERENCE_OUTPUTS)["score"] == 1
    assert invented_urls_absent(outputs=outputs, reference_outputs=REFERENCE_OUTPUTS)["score"] == 1


def test_code_evaluators_flag_missing_terms_and_invented_url() -> None:
    outputs = {
        "answer": "LI Xin is the only LI Xin. Read more at https://example.com/li-xin."
    }

    assert required_terms_present(outputs=outputs, reference_outputs=REFERENCE_OUTPUTS)["score"] == 0
    assert forbidden_terms_absent(outputs=outputs, reference_outputs=REFERENCE_OUTPUTS)["score"] == 0
    assert invented_urls_absent(outputs=outputs, reference_outputs=REFERENCE_OUTPUTS)["score"] == 0
