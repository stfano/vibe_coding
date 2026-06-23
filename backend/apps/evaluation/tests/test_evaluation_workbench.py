from __future__ import annotations

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.evaluation.models import EvaluationCase, EvaluationDataset, EvaluationResult, EvaluationRun
from apps.evaluation.services import run_evaluation_dataset, seed_hidoc_smoke_dataset
from apps.knowledge.indexing import ExternalQnaIndexer
from apps.knowledge.models import ExternalQnaRecord, KnowledgeDocument
from apps.rag.embeddings import DeterministicEmbeddingAdapter
from apps.rag.retrieval import KnowledgeSearchResult


@pytest.fixture
def ready_hidoc_document() -> KnowledgeDocument:
    record = ExternalQnaRecord.objects.create(
        source="hidoc",
        external_id="hidoc:EVAL100:A100",
        content_hash="eval-hash-1",
        department="소아청소년과",
        source_department_code="PD000",
        source_question_id="EVAL100",
        source_answer_id="A100",
        source_url="https://www.hidoc.co.kr/healthqna/view/EVAL100",
        list_page=1,
        question_title="아기 고환 물집 평가",
        question_body="아기띠 후 고환에 물집처럼 보이는 증상이 있습니다.",
        answer_body="압박으로 인한 일시 변화일 수 있으나 진료를 권합니다.",
        answerer_name="평가의",
        answerer_title="전문의",
        tags=["영유아"],
        collected_at=timezone.now(),
    )
    ExternalQnaIndexer(
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        chunk_chars=320,
    ).index_records(ExternalQnaRecord.objects.filter(pk=record.pk))
    document = KnowledgeDocument.objects.get(source_external_id=record.external_id)
    document.status = KnowledgeDocument.Status.READY
    document.save(update_fields=["status"])
    return document


def _create_ready_document(*, external_id: str, question_id: str, title: str) -> KnowledgeDocument:
    record = ExternalQnaRecord.objects.create(
        source="hidoc",
        external_id=external_id,
        content_hash=f"{external_id}-hash",
        department="소아청소년과",
        source_department_code="PD000",
        source_question_id=question_id,
        source_answer_id="A100",
        source_url=f"https://www.hidoc.co.kr/healthqna/view/{question_id}",
        list_page=1,
        question_title=title,
        question_body=f"{title} 증상 관련 질문입니다.",
        answer_body=f"{title} 관련 답변입니다.",
        answerer_name="평가의",
        answerer_title="전문의",
        tags=["영유아"],
        collected_at=timezone.now(),
    )
    ExternalQnaIndexer(
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        chunk_chars=320,
    ).index_records(ExternalQnaRecord.objects.filter(pk=record.pk))
    document = KnowledgeDocument.objects.get(source_external_id=record.external_id)
    document.status = KnowledgeDocument.Status.READY
    document.save(update_fields=["status"])
    return document


@pytest.mark.django_db
def test_seed_hidoc_smoke_dataset_is_idempotent_and_uses_ready_document(ready_hidoc_document):
    first = seed_hidoc_smoke_dataset(
        dataset_name="hidoc-pediatric-smoke",
        source="hidoc",
        department_code="PD000",
    )
    second = seed_hidoc_smoke_dataset(
        dataset_name="hidoc-pediatric-smoke",
        source="hidoc",
        department_code="PD000",
    )

    dataset = EvaluationDataset.objects.get(name="hidoc-pediatric-smoke")
    cases = list(dataset.cases.order_by("case_key"))
    assert first["dataset_id"] == second["dataset_id"] == dataset.id
    assert first["created_or_updated"] == second["created_or_updated"]
    assert EvaluationCase.objects.count() == 4
    assert {case.expected_source_status for case in cases} == {
        "retrieved",
        "no_matching_ready_documents",
        "low_confidence",
        "urgent_escalation",
    }
    retrieved = EvaluationCase.objects.get(case_key="hidoc-ready-retrieved")
    assert retrieved.expected_citation_external_ids == ["EVAL100:A100"]
    assert retrieved.expected_source_document_ids == [ready_hidoc_document.id]


@pytest.mark.django_db
def test_seed_hidoc_smoke_dataset_reports_ready_case_skipped_when_no_ready_docs():
    summary = seed_hidoc_smoke_dataset(
        dataset_name="hidoc-pediatric-smoke",
        source="hidoc",
        department_code="PD000",
    )

    dataset = EvaluationDataset.objects.get(name="hidoc-pediatric-smoke")
    assert summary["skipped_ready_cases"] == 2
    assert set(dataset.cases.values_list("case_key", flat=True)) == {
        "hidoc-no-ready-docs",
        "hidoc-red-flag",
    }


@pytest.mark.django_db
def test_seed_hidoc_smoke_dataset_prefers_ready_document_that_retrieves_itself(monkeypatch):
    first = _create_ready_document(external_id="hidoc:EVAL201:A100", question_id="EVAL201", title="첫 번째 문서")
    second = _create_ready_document(external_id="hidoc:EVAL202:A100", question_id="EVAL202", title="두 번째 문서")

    def fake_search_knowledge(query, **kwargs):
        if "두 번째" in query:
            return [
                KnowledgeSearchResult(
                    chunk_id=second.chunks.first().id,
                    document_id=second.id,
                    document_status=second.status,
                    score=0.9,
                    text_preview="두 번째 문서",
                    citation=second.chunks.first().citation_metadata,
                )
            ]
        return [
            KnowledgeSearchResult(
                chunk_id=second.chunks.first().id,
                document_id=second.id,
                document_status=second.status,
                score=0.7,
                text_preview="두 번째 문서",
                citation=second.chunks.first().citation_metadata,
            )
        ]

    monkeypatch.setattr("apps.evaluation.services.search_knowledge", fake_search_knowledge)

    seed_hidoc_smoke_dataset(
        dataset_name="hidoc-pediatric-smoke",
        source="hidoc",
        department_code="PD000",
    )

    retrieved = EvaluationCase.objects.get(case_key="hidoc-ready-retrieved")
    assert retrieved.expected_source_document_ids == [second.id]
    assert retrieved.query.startswith("두 번째")
    assert first.id not in retrieved.expected_source_document_ids


@pytest.mark.django_db
def test_run_evaluation_dataset_persists_deterministic_results(ready_hidoc_document):
    seed_hidoc_smoke_dataset(
        dataset_name="hidoc-pediatric-smoke",
        source="hidoc",
        department_code="PD000",
    )

    run = run_evaluation_dataset(
        dataset_name="hidoc-pediatric-smoke",
        llm_provider="deterministic",
        model_name="deterministic-eval-llm",
    )

    run.refresh_from_db()
    assert run.status == EvaluationRun.Status.SUCCEEDED
    assert run.total_cases == 4
    assert run.passed_cases == 4
    assert run.failed_cases == 0
    retrieved = EvaluationResult.objects.get(run=run, case__case_key="hidoc-ready-retrieved")
    assert retrieved.status == EvaluationResult.Status.PASSED
    assert retrieved.source_status == "retrieved"
    assert retrieved.llm_executed is True
    assert retrieved.model_name == "deterministic-eval-llm"
    assert retrieved.prompt_version
    assert retrieved.graph_metadata["runtime"] == "langgraph_stategraph"
    assert retrieved.citations[0]["external_question_id"] == "EVAL100"
    assert retrieved.retrieved_source_ids == [ready_hidoc_document.id]
    assert "synthesize_answer" in retrieved.graph_path


@pytest.mark.django_db
def test_run_evaluation_dataset_checks_fallback_branches_do_not_execute_llm(ready_hidoc_document):
    seed_hidoc_smoke_dataset(
        dataset_name="hidoc-pediatric-smoke",
        source="hidoc",
        department_code="PD000",
    )

    run = run_evaluation_dataset(dataset_name="hidoc-pediatric-smoke", llm_provider="deterministic")

    red_flag = EvaluationResult.objects.get(run=run, case__case_key="hidoc-red-flag")
    no_ready = EvaluationResult.objects.get(run=run, case__case_key="hidoc-no-ready-docs")
    low_confidence = EvaluationResult.objects.get(run=run, case__case_key="hidoc-low-confidence")
    assert red_flag.source_status == "urgent_escalation"
    assert red_flag.llm_executed is False
    assert no_ready.source_status == "no_matching_ready_documents"
    assert no_ready.llm_executed is False
    assert low_confidence.source_status == "low_confidence"
    assert low_confidence.llm_executed is False


@pytest.mark.django_db
def test_run_chat_eval_management_command_prints_summary(ready_hidoc_document, capsys):
    call_command(
        "seed_eval_cases",
        dataset="hidoc-pediatric-smoke",
        source="hidoc",
        department_code="PD000",
    )

    call_command("run_chat_eval", dataset="hidoc-pediatric-smoke", llm_provider="deterministic")

    output = capsys.readouterr().out
    assert "dataset=hidoc-pediatric-smoke" in output
    assert "total=4 passed=4 failed=0 skipped=0" in output


@pytest.mark.django_db
def test_evaluation_api_lists_datasets_and_run_details(ready_hidoc_document):
    seed_hidoc_smoke_dataset(
        dataset_name="hidoc-pediatric-smoke",
        source="hidoc",
        department_code="PD000",
    )
    run = run_evaluation_dataset(dataset_name="hidoc-pediatric-smoke", llm_provider="deterministic")

    client = APIClient()
    datasets = client.get(reverse("evaluation-dataset-list"))
    runs = client.get(reverse("evaluation-run-list"))
    detail = client.get(reverse("evaluation-run-detail", args=[run.id]))

    assert datasets.status_code == 200
    assert datasets.json()["ok"] is True
    assert datasets.json()["data"]["results"][0]["name"] == "hidoc-pediatric-smoke"
    assert runs.status_code == 200
    assert runs.json()["data"]["results"][0]["id"] == run.id
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["run"]["id"] == run.id
    assert len(detail_data["results"]) == 4
    assert detail_data["results"][0]["graph_path"]


@pytest.mark.django_db
def test_low_confidence_threshold_override_is_restored(ready_hidoc_document):
    seed_hidoc_smoke_dataset(
        dataset_name="hidoc-pediatric-smoke",
        source="hidoc",
        department_code="PD000",
    )

    with override_settings(CHAT_RAG_LOW_CONFIDENCE_THRESHOLD=0.05):
        run = run_evaluation_dataset(dataset_name="hidoc-pediatric-smoke", llm_provider="deterministic")

    low_confidence = EvaluationResult.objects.get(run=run, case__case_key="hidoc-low-confidence")
    assert low_confidence.source_status == "low_confidence"
