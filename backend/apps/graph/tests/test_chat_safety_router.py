from __future__ import annotations

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.graph.router import run_chat_safety_graph
from apps.knowledge.indexing import ExternalQnaIndexer
from apps.knowledge.models import ExternalQnaRecord, KnowledgeDocument
from apps.rag.embeddings import DeterministicEmbeddingAdapter
from apps.rag.llms import LLMResponse


class RecordingLLMAdapter:
    model_name = "recording-llm"

    def __init__(self):
        self.calls = []

    def generate_answer(self, payload):
        self.calls.append(payload)
        return LLMResponse(text="생성된 근거 기반 답변입니다. [1]", model_name=self.model_name)


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
    llm_adapter = RecordingLLMAdapter()

    result = run_chat_safety_graph(
        message="소아 호흡곤란 청색증 응급",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        llm_adapter=llm_adapter,
    )

    assert result["source_status"] == "urgent_escalation"
    assert result["llm_executed"] is False
    assert llm_adapter.calls == []
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
    llm_adapter = RecordingLLMAdapter()

    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        llm_adapter=llm_adapter,
    )

    assert result["source_status"] == "retrieved"
    assert result["answer"] == "생성된 근거 기반 답변입니다. [1]"
    assert result["llm_executed"] is True
    assert result["citations"][0]["external_question_id"] == "GRAPH100"
    assert result["retrieved_source_ids"] == [ready_document.id]
    assert result["graph"]["executed"] is True
    assert result["graph"]["model_name"] == "recording-llm"
    assert result["graph"]["prompt_version"]
    assert result["graph"]["node_summaries"]
    assert "synthesize_answer" in result["graph"]["path"]
    assert len(llm_adapter.calls) == 1


@pytest.mark.django_db
def test_chat_safety_graph_prompt_payload_contains_only_query_context_and_citations(ready_document):
    llm_adapter = RecordingLLMAdapter()

    run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        llm_adapter=llm_adapter,
    )

    payload = llm_adapter.calls[0]
    assert payload["query"] == "아기 고환 물집 아기띠"
    assert set(payload) == {"prompt_version", "instructions", "query", "contexts"}
    assert len(payload["contexts"]) == 1
    assert set(payload["contexts"][0]) == {"chunk_id", "document_id", "score", "text", "citation"}
    assert payload["contexts"][0]["citation"]["external_question_id"] == "GRAPH100"
    assert "아기띠" in payload["contexts"][0]["text"]
    assert "question_body" not in payload["contexts"][0]
    assert "answer_body" not in payload["contexts"][0]


@pytest.mark.django_db
def test_chat_safety_graph_low_confidence_fallback(ready_document):
    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
    )
    # Re-run with a deliberately high threshold to pin the low-confidence branch.
    llm_adapter = RecordingLLMAdapter()
    with override_settings(CHAT_RAG_LOW_CONFIDENCE_THRESHOLD=result["retrieved_chunks"][0]["score"] + 0.1):
        low_confidence = run_chat_safety_graph(
            message="아기 고환 물집 아기띠",
            embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
            llm_adapter=llm_adapter,
        )

    assert low_confidence["source_status"] == "low_confidence"
    assert low_confidence["llm_executed"] is False
    assert "low_confidence_retrieval" in low_confidence["safety_flags"]
    assert llm_adapter.calls == []


@pytest.mark.django_db
def test_chat_safety_graph_no_ready_docs_does_not_call_llm(ready_document):
    ready_document.status = KnowledgeDocument.Status.NEEDS_REVIEW
    ready_document.save(update_fields=["status"])
    llm_adapter = RecordingLLMAdapter()

    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        llm_adapter=llm_adapter,
    )

    assert result["source_status"] == "no_matching_ready_documents"
    assert result["llm_executed"] is False
    assert llm_adapter.calls == []
