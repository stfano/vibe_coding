from __future__ import annotations

import pytest
from django.utils import timezone

from apps.knowledge.indexing import ExternalQnaIndexer
from apps.knowledge.models import ExternalQnaRecord
from apps.rag.embeddings import DeterministicEmbeddingAdapter, build_embedding_payload
from apps.rag.retrieval import search_knowledge


@pytest.fixture
def indexed_qna_record() -> ExternalQnaRecord:
    record = ExternalQnaRecord.objects.create(
        source="hidoc",
        external_id="hidoc:C0002:A0002",
        content_hash="hash-2",
        department="소아청소년과",
        source_department_code="PD000",
        source_question_id="C0002",
        source_answer_id="A0002",
        source_url="https://www.hidoc.co.kr/healthqna/view/C0002",
        list_page=1,
        question_title="아기띠 후 고환 물집",
        question_body="아기띠를 하고 나면 고환에 물집처럼 보입니다.",
        answer_body="소아청소년과 진료를 권하고 압박을 줄이는 착용법을 고려합니다.",
        collected_at=timezone.now(),
    )
    ExternalQnaIndexer(
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
        chunk_chars=320,
    ).index_records(ExternalQnaRecord.objects.filter(pk=record.pk))
    return record


def test_embedding_payload_shape_uses_model_from_adapter():
    payload = build_embedding_payload(["아기 고환 물집"], model="test-model", dimensions=8)

    assert payload == {
        "texts": ["아기 고환 물집"],
        "model": "test-model",
        "dimensions": 8,
    }


def test_deterministic_embedding_adapter_returns_stable_dimensions():
    adapter = DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding")

    first = adapter.embed_texts(["아기 고환 물집"])[0]
    second = adapter.embed_texts(["아기 고환 물집"])[0]

    assert len(first) == 8
    assert first == second


@pytest.mark.django_db
def test_search_knowledge_returns_chunk_preview_and_citation(indexed_qna_record):
    results = search_knowledge(
        "아기 고환 물집 아기띠",
        top_k=3,
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
    )

    assert len(results) == 1
    assert "아기띠" in results[0].text_preview
    assert results[0].citation["source"] == "hidoc"
    assert results[0].citation["external_question_id"] == "C0002"
    assert results[0].citation["external_answer_id"] == "A0002"
    assert results[0].score >= 0


@pytest.mark.django_db
def test_search_knowledge_returns_empty_list_when_no_chunks():
    assert search_knowledge(
        "검색 결과 없음",
        top_k=5,
        embedding_adapter=DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding"),
    ) == []
