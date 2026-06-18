from __future__ import annotations

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.graph.router import run_chat_safety_graph
from apps.knowledge.indexing import ExternalQnaIndexer
from apps.knowledge.models import ExternalQnaRecord, KnowledgeDocument
from apps.rag.embeddings import DeterministicEmbeddingAdapter


@pytest.fixture
def ready_document() -> KnowledgeDocument:
    record = ExternalQnaRecord.objects.create(
        source="hidoc",
        external_id="hidoc:GRAPH100:A100",
        content_hash="graph-hash-1",
        department="소아청소년과",
        source_department_code="PD000",
        source_question_id="GRAPH100",
        source_answer_id="A100",
        source_url="https://www.hidoc.co.kr/healthqna/view/GRAPH100",
        list_page=1,
        question_title="아기 고환 물집",
        question_body="아기띠 후 고환에 물집처럼 보이는 증상이 있습니다.",
        answer_body="압박으로 인한 일시 변화일 수 있으나 진료를 권합니다.",
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
def test_chat_safety_graph_suppresses_red_flag_before_retrieval(ready_document):
    result = run_chat_safety_graph(
        message="소아 호흡곤란 청색증 응급",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
    )

    assert result["source_status"] == "urgent_escalation"
    assert result["citations"] == []
    assert "red_flag_query" in result["safety_flags"]
    assert result["graph"]["path"] == [
        "validate_input",
        "detect_red_flags",
        "decide_source_status",
        "format_response",
        "persist_metadata",
    ]


@pytest.mark.django_db
def test_chat_safety_graph_returns_ready_context_with_citations(ready_document):
    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
    )

    assert result["source_status"] == "retrieved"
    assert result["citations"][0]["external_question_id"] == "GRAPH100"
    assert result["retrieved_source_ids"] == [ready_document.id]
    assert result["graph"]["executed"] is True
    assert result["graph"]["node_summaries"]


@pytest.mark.django_db
def test_chat_safety_graph_low_confidence_fallback(ready_document):
    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
    )
    # Re-run with a deliberately high threshold to pin the low-confidence branch.
    with override_settings(CHAT_RAG_LOW_CONFIDENCE_THRESHOLD=result["retrieved_chunks"][0]["score"] + 0.1):
        low_confidence = run_chat_safety_graph(
            message="아기 고환 물집 아기띠",
            embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        )

    assert low_confidence["source_status"] == "low_confidence"
    assert "low_confidence_retrieval" in low_confidence["safety_flags"]
