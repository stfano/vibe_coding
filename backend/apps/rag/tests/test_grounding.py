from __future__ import annotations

from apps.rag.grounding import review_grounded_answer


def test_review_grounded_answer_passes_known_citation_id():
    review = review_grounded_answer(
        answer="근거 문서에 따르면 진료 평가가 필요합니다. Citations: C100:A100",
        contexts=[
            {
                "citation": {
                    "external_question_id": "C100",
                    "external_answer_id": "A100",
                },
                "text": "진료 평가가 필요합니다.",
            }
        ],
    )

    assert review.status == "passed"
    assert review.findings == []
    assert review.allowed_citation_ids == ["C100:A100", "C100", "[1]"]
    assert review.detected_citation_ids == ["C100:A100"]


def test_review_grounded_answer_fails_missing_known_citation():
    review = review_grounded_answer(
        answer="근거 문서 요약이지만 citation이 없습니다.",
        contexts=[{"citation": {"external_question_id": "C100", "external_answer_id": "A100"}, "text": ""}],
    )

    assert review.status == "failed"
    assert "missing_known_citation" in review.findings


def test_review_grounded_answer_fails_unknown_citation():
    review = review_grounded_answer(
        answer="근거 문서 요약입니다. Citations: X999:A999",
        contexts=[{"citation": {"external_question_id": "C100", "external_answer_id": "A100"}, "text": ""}],
    )

    assert review.status == "failed"
    assert "unknown_citation" in review.findings
    assert review.unknown_citation_ids == ["X999:A999"]


def test_review_grounded_answer_fails_definitive_diagnosis_language():
    review = review_grounded_answer(
        answer="진단됩니다. Citations: C100:A100",
        contexts=[{"citation": {"external_question_id": "C100", "external_answer_id": "A100"}, "text": ""}],
    )

    assert review.status == "failed"
    assert "definitive_diagnosis_language" in review.findings


def test_review_grounded_answer_fails_unsupported_answer_dose():
    review = review_grounded_answer(
        answer="아세트아미노펜 10mg/kg를 시작하세요. Citations: C100:A100",
        contexts=[
            {
                "citation": {
                    "external_question_id": "C100",
                    "external_answer_id": "A100",
                },
                "text": "진료 평가가 필요합니다.",
            }
        ],
    )

    assert review.status == "failed"
    assert "unsupported_medication_dose" in review.findings


def test_review_grounded_answer_fails_unsupported_prescription_language_without_dose():
    review = review_grounded_answer(
        answer="항생제를 시작하세요. Citations: C100:A100",
        contexts=[
            {
                "citation": {
                    "external_question_id": "C100",
                    "external_answer_id": "A100",
                },
                "text": "진료 평가가 필요합니다.",
            }
        ],
    )

    assert review.status == "failed"
    assert "unsupported_prescription_language" in review.findings


def test_review_grounded_answer_ignores_uppercase_medical_terms_with_numbers():
    review = review_grounded_answer(
        answer="COVID19 병력은 문진으로 확인합니다. Citations: C100:A100",
        contexts=[
            {
                "citation": {
                    "external_question_id": "C100",
                    "external_answer_id": "A100",
                },
                "text": "COVID19 병력은 문진으로 확인합니다.",
            }
        ],
    )

    assert review.status == "passed"
    assert review.unknown_citation_ids == []
