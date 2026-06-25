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

    def __init__(self, response_text: str = "생성된 근거 기반 답변입니다. Citations: GRAPH100:A100"):
        self.calls = []
        self.response_text = response_text

    def generate_answer(self, payload):
        self.calls.append(payload)
        return LLMResponse(text=self.response_text, model_name=self.model_name)


class FailingEmbeddingAdapter:
    model_name = "failing-embedding"

    def embed_query(self, text):
        raise RuntimeError("simulated embedding transport failure with sensitive details")


class FailingLLMAdapter:
    model_name = "failing-llm"

    def __init__(self):
        self.calls = 0

    def generate_answer(self, payload):
        self.calls += 1
        raise RuntimeError("simulated llm provider failure with sensitive details")


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
    assert result["answer"] == "생성된 근거 기반 답변입니다. Citations: GRAPH100:A100"
    assert result["llm_executed"] is True
    assert result["citations"][0]["external_question_id"] == "GRAPH100"
    assert result["retrieved_source_ids"] == [ready_document.id]
    assert result["graph"]["executed"] is True
    assert result["graph"]["runtime"] == "langgraph_stategraph"
    assert result["graph"]["model_name"] == "recording-llm"
    assert result["graph"]["prompt_version"]
    assert result["graph"]["answer_safety_status"] == "passed"
    assert result["graph"]["answer_safety_findings"] == []
    assert result["graph"]["node_summaries"]
    assert "synthesize_answer" in result["graph"]["path"]
    assert "safety_review" in result["graph"]["path"]
    assert len(llm_adapter.calls) == 1


@pytest.mark.django_db
def test_chat_safety_graph_blocks_retrieved_answer_without_citation(ready_document):
    llm_adapter = RecordingLLMAdapter(response_text="생성된 답변이지만 출처 표기가 없습니다.")

    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        llm_adapter=llm_adapter,
    )

    assert result["source_status"] == "answer_grounding_failed"
    assert result["llm_executed"] is True
    assert result["citations"][0]["external_question_id"] == "GRAPH100"
    assert result["retrieved_source_ids"] == [ready_document.id]
    assert "answer_grounding_failed" in result["safety_flags"]
    assert result["graph"]["answer_safety_status"] == "failed"
    assert "missing_known_citation" in result["graph"]["answer_safety_findings"]
    assert "failed grounding checks" in result["answer"]
    assert "출처 표기가 없습니다" not in result["answer"]


@pytest.mark.django_db
def test_chat_safety_graph_blocks_retrieved_answer_with_unknown_citation(ready_document):
    llm_adapter = RecordingLLMAdapter(response_text="생성된 답변입니다. Citations: WRONG:A999")

    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        llm_adapter=llm_adapter,
    )

    assert result["source_status"] == "answer_grounding_failed"
    assert result["llm_executed"] is True
    assert "answer_grounding_failed" in result["safety_flags"]
    assert result["graph"]["answer_safety_status"] == "failed"
    assert "unknown_citation" in result["graph"]["answer_safety_findings"]


@pytest.mark.django_db
def test_chat_safety_graph_blocks_definitive_diagnosis_language(ready_document):
    llm_adapter = RecordingLLMAdapter(response_text="진단됩니다. Citations: GRAPH100:A100")

    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        llm_adapter=llm_adapter,
    )

    assert result["source_status"] == "answer_grounding_failed"
    assert "answer_definitive_diagnosis_language" in result["safety_flags"]
    assert "definitive_diagnosis_language" in result["graph"]["answer_safety_findings"]


@pytest.mark.django_db
def test_chat_safety_graph_blocks_unsupported_medication_dose(ready_document):
    llm_adapter = RecordingLLMAdapter(response_text="아세트아미노펜 10mg/kg를 하루 3회 시작하세요. Citations: GRAPH100:A100")

    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        llm_adapter=llm_adapter,
    )

    assert result["source_status"] == "answer_grounding_failed"
    assert "answer_unsupported_medication_dose" in result["safety_flags"]
    assert "unsupported_medication_dose" in result["graph"]["answer_safety_findings"]


@pytest.mark.django_db
def test_chat_safety_graph_blocks_unsupported_prescription_language(ready_document):
    llm_adapter = RecordingLLMAdapter(response_text="항생제를 시작하세요. Citations: GRAPH100:A100")

    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        llm_adapter=llm_adapter,
    )

    assert result["source_status"] == "answer_grounding_failed"
    assert "answer_unsupported_prescription_language" in result["safety_flags"]
    assert "unsupported_prescription_language" in result["graph"]["answer_safety_findings"]


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
        llm_adapter=RecordingLLMAdapter(),
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
    assert low_confidence["graph"]["answer_safety_status"] == "skipped"
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
    assert result["graph"]["answer_safety_status"] == "skipped"
    assert llm_adapter.calls == []


@pytest.mark.django_db
def test_chat_safety_graph_returns_safe_metadata_when_retrieval_fails(ready_document):
    llm_adapter = RecordingLLMAdapter()

    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=FailingEmbeddingAdapter(),
        llm_adapter=llm_adapter,
    )

    assert result["source_status"] == "graph_error"
    assert result["llm_executed"] is False
    assert llm_adapter.calls == []
    assert result["citations"] == []
    assert result["retrieved_source_ids"] == []
    assert "graph_error" in result["safety_flags"]
    assert "could not complete" in result["answer"]
    assert "simulated embedding" not in result["answer"]
    assert result["graph"]["error_summary"] == "retrieve_ready_documents failed"
    assert result["graph"]["path"] == [
        "validate_input",
        "detect_red_flags",
        "retrieve_ready_documents",
        "format_response",
        "persist_metadata",
    ]


@pytest.mark.django_db
def test_chat_safety_graph_returns_safe_metadata_when_llm_fails(ready_document):
    llm_adapter = FailingLLMAdapter()

    result = run_chat_safety_graph(
        message="아기 고환 물집 아기띠",
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        llm_adapter=llm_adapter,
    )

    assert result["source_status"] == "graph_error"
    assert result["llm_executed"] is False
    assert llm_adapter.calls == 1
    assert result["citations"][0]["external_question_id"] == "GRAPH100"
    assert result["retrieved_source_ids"] == [ready_document.id]
    assert "graph_error" in result["safety_flags"]
    assert "simulated llm" not in result["answer"]
    assert result["graph"]["error_summary"] == "synthesize_answer failed"
    assert result["graph"]["model_name"] is None
    assert result["graph"]["prompt_version"] is None
