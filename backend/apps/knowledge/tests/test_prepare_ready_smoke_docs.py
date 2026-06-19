from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.evaluation.models import EvaluationCase
from apps.evaluation.services import run_evaluation_dataset, seed_hidoc_smoke_dataset
from apps.knowledge.indexing import ExternalQnaIndexer
from apps.knowledge.models import ExternalQnaRecord, KnowledgeDocument
from apps.rag.embeddings import DeterministicEmbeddingAdapter


def _create_indexed_document(
    *,
    external_id: str,
    question_id: str,
    answer_id: str,
    title: str = "아기 고환 물집 검수",
    body_suffix: str = "",
) -> KnowledgeDocument:
    record = ExternalQnaRecord.objects.create(
        source="hidoc",
        external_id=external_id,
        content_hash=f"hash-{question_id}-{answer_id}",
        department="소아청소년과",
        source_department_code="PD000",
        source_question_id=question_id,
        source_answer_id=answer_id,
        source_url=f"https://www.hidoc.co.kr/healthqna/view/{question_id}",
        list_page=1,
        question_title=title,
        question_body=(
            "아기띠 후 고환에 물집처럼 보이는 증상이 있습니다. "
            "이 문장은 전체 원문 노출 방지 검증을 위해 충분히 길게 둡니다. "
            f"{body_suffix}"
        ),
        answer_body="압박으로 인한 일시 변화일 수 있으나 진료를 권합니다.",
        answerer_name="검수의",
        answerer_title="전문의",
        tags=["영유아"],
        collected_at=timezone.now(),
    )
    ExternalQnaIndexer(
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        chunk_chars=320,
    ).index_records(ExternalQnaRecord.objects.filter(pk=record.pk))
    return KnowledgeDocument.objects.get(source_external_id=record.external_id)


@pytest.mark.django_db
def test_prepare_ready_smoke_docs_dry_run_lists_only_reviewable_candidates():
    candidate = _create_indexed_document(
        external_id="hidoc:READY001:ANSWER001",
        question_id="READY001",
        answer_id="ANSWER001",
    )
    disabled = _create_indexed_document(
        external_id="hidoc:DISABLED001:ANSWER001",
        question_id="DISABLED001",
        answer_id="ANSWER001",
    )
    disabled.status = KnowledgeDocument.Status.DISABLED
    disabled.save(update_fields=["status"])
    no_chunk = _create_indexed_document(
        external_id="hidoc:NOCHUNK001:ANSWER001",
        question_id="NOCHUNK001",
        answer_id="ANSWER001",
    )
    no_chunk.chunks.all().delete()
    no_citation = _create_indexed_document(
        external_id="hidoc:NOCITE001:ANSWER001",
        question_id="NOCITE001",
        answer_id="ANSWER001",
    )
    no_citation.chunks.update(citation_metadata={})

    output = StringIO()
    call_command(
        "prepare_ready_smoke_docs",
        source="hidoc",
        department_code="PD000",
        limit=10,
        dry_run=True,
        stdout=output,
    )

    text = output.getvalue()
    assert f"document_id={candidate.id}" in text
    assert f"document_id={disabled.id}" not in text
    assert f"document_id={no_chunk.id}" not in text
    assert f"document_id={no_citation.id}" not in text
    assert "external_question_id=READY001" in text
    assert "chunk_count=1" in text


@pytest.mark.django_db
def test_prepare_ready_smoke_docs_dry_run_does_not_modify_status_or_print_full_body():
    document = _create_indexed_document(
        external_id="hidoc:DRYRUN001:ANSWER001",
        question_id="DRYRUN001",
        answer_id="ANSWER001",
        body_suffix="민감한 전체 본문 문장 노출 금지 테스트",
    )

    output = StringIO()
    call_command(
        "prepare_ready_smoke_docs",
        source="hidoc",
        department_code="PD000",
        document_id=str(document.id),
        mark_ready=True,
        confirm=True,
        dry_run=True,
        stdout=output,
    )

    document.refresh_from_db()
    text = output.getvalue()
    assert document.status == KnowledgeDocument.Status.NEEDS_REVIEW
    assert "would_change=1" in text
    assert "민감한 전체 본문 문장 노출 금지 테스트" not in text


@pytest.mark.django_db
def test_prepare_ready_smoke_docs_mark_ready_requires_explicit_document_and_confirm():
    selected = _create_indexed_document(
        external_id="hidoc:SELECTED001:ANSWER001",
        question_id="SELECTED001",
        answer_id="ANSWER001",
    )
    untouched = _create_indexed_document(
        external_id="hidoc:UNTOUCHED001:ANSWER001",
        question_id="UNTOUCHED001",
        answer_id="ANSWER001",
    )
    unselected = _create_indexed_document(
        external_id="hidoc:UNSELECTED001:ANSWER001",
        question_id="UNSELECTED001",
        answer_id="ANSWER001",
    )

    output = StringIO()
    call_command(
        "prepare_ready_smoke_docs",
        source="hidoc",
        department_code="PD000",
        document_id=f"{selected.id},{untouched.id}",
        mark_ready=True,
        confirm=True,
        stdout=output,
    )

    selected.refresh_from_db()
    untouched.refresh_from_db()
    unselected.refresh_from_db()
    assert selected.status == KnowledgeDocument.Status.READY
    assert untouched.status == KnowledgeDocument.Status.READY
    assert unselected.status == KnowledgeDocument.Status.NEEDS_REVIEW
    assert "changed=2" in output.getvalue()


@pytest.mark.django_db
def test_prepare_ready_smoke_docs_reverts_ready_document_to_needs_review():
    document = _create_indexed_document(
        external_id="hidoc:REVERT001:ANSWER001",
        question_id="REVERT001",
        answer_id="ANSWER001",
    )
    document.status = KnowledgeDocument.Status.READY
    document.save(update_fields=["status"])

    output = StringIO()
    call_command(
        "prepare_ready_smoke_docs",
        source="hidoc",
        department_code="PD000",
        document_id=str(document.id),
        mark_needs_review=True,
        confirm=True,
        stdout=output,
    )

    document.refresh_from_db()
    assert document.status == KnowledgeDocument.Status.NEEDS_REVIEW
    assert "changed=1" in output.getvalue()


@pytest.mark.django_db
def test_seed_and_deterministic_eval_include_four_cases_after_ready_promotion():
    document = _create_indexed_document(
        external_id="hidoc:EVALREADY001:ANSWER001",
        question_id="EVALREADY001",
        answer_id="ANSWER001",
    )
    call_command(
        "prepare_ready_smoke_docs",
        source="hidoc",
        department_code="PD000",
        document_id=str(document.id),
        mark_ready=True,
        confirm=True,
        stdout=StringIO(),
    )

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

    assert EvaluationCase.objects.filter(is_active=True).count() == 4
    assert run.total_cases == 4
    assert run.passed_cases == 4
    assert run.failed_cases == 0
    retrieved = run.results.get(case__case_key="hidoc-ready-retrieved")
    assert retrieved.source_status == "retrieved"
    assert retrieved.llm_executed is True
    assert retrieved.citations
    assert retrieved.retrieved_source_ids == [document.id]
    no_ready = run.results.get(case__case_key="hidoc-no-ready-docs")
    red_flag = run.results.get(case__case_key="hidoc-red-flag")
    assert no_ready.llm_executed is False
    assert red_flag.llm_executed is False
