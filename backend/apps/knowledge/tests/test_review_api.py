from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.knowledge.indexing import ExternalQnaIndexer
from apps.knowledge.models import ExternalQnaRecord, KnowledgeDocument
from apps.rag.embeddings import DeterministicEmbeddingAdapter


@pytest.fixture
def indexed_document() -> KnowledgeDocument:
    record = ExternalQnaRecord.objects.create(
        source="hidoc",
        external_id="hidoc:C1000:A1000",
        content_hash="hash-review",
        department="소아청소년과",
        source_department_code="PD000",
        source_question_id="C1000",
        source_answer_id="A1000",
        source_url="https://www.hidoc.co.kr/healthqna/view/C1000",
        list_page=1,
        question_title="아기 고환 물집 검수",
        question_body="아기띠 후 고환에 물집처럼 보이는 증상이 있습니다.",
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
def test_knowledge_document_list_filters_by_source_department_and_status(indexed_document):
    response = APIClient().get(
        reverse("knowledge-document-list"),
        {
            "source": "hidoc",
            "department_code": "PD000",
            "status": KnowledgeDocument.Status.NEEDS_REVIEW,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["count"] == 1
    assert body["data"]["results"][0]["id"] == indexed_document.id
    assert body["data"]["results"][0]["status"] == KnowledgeDocument.Status.NEEDS_REVIEW
    assert body["data"]["results"][0]["chunk_count"] == 1


@pytest.mark.django_db
def test_knowledge_document_detail_includes_external_record_and_chunks(indexed_document):
    response = APIClient().get(reverse("knowledge-document-detail", args=[indexed_document.id]))

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["document"]["id"] == indexed_document.id
    assert body["data"]["external_qna_record"]["source_question_id"] == "C1000"
    assert body["data"]["external_qna_record"]["question_title"] == "아기 고환 물집 검수"
    assert body["data"]["chunks"][0]["citation_metadata"]["external_answer_id"] == "A1000"


@pytest.mark.django_db
def test_knowledge_document_status_update_changes_status(indexed_document):
    response = APIClient().patch(
        reverse("knowledge-document-status", args=[indexed_document.id]),
        {"status": KnowledgeDocument.Status.READY},
        format="json",
    )

    assert response.status_code == 200
    indexed_document.refresh_from_db()
    assert indexed_document.status == KnowledgeDocument.Status.READY
    assert response.json()["data"]["status"] == KnowledgeDocument.Status.READY


@pytest.mark.django_db
def test_knowledge_document_status_update_rejects_invalid_status(indexed_document):
    response = APIClient().patch(
        reverse("knowledge-document-status", args=[indexed_document.id]),
        {"status": "approved"},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_document_status"


@pytest.mark.django_db
def test_retrieval_verification_search_returns_ready_documents_only_by_default(indexed_document):
    response = APIClient().get(
        reverse("knowledge-search-verify"),
        {"query": "아기 고환 물집 아기띠", "source": "hidoc", "department_code": "PD000"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["results"] == []

    indexed_document.status = KnowledgeDocument.Status.READY
    indexed_document.save(update_fields=["status"])

    response = APIClient().get(
        reverse("knowledge-search-verify"),
        {"query": "아기 고환 물집 아기띠", "source": "hidoc", "department_code": "PD000"},
    )

    assert response.status_code == 200
    result = response.json()["data"]["results"][0]
    assert result["document_status"] == KnowledgeDocument.Status.READY
    assert result["citation"]["external_question_id"] == "C1000"


@pytest.mark.django_db
def test_retrieval_verification_can_include_needs_review_for_admin_mode(indexed_document):
    response = APIClient().get(
        reverse("knowledge-search-verify"),
        {
            "query": "아기 고환 물집 아기띠",
            "source": "hidoc",
            "department_code": "PD000",
            "include_needs_review": "true",
        },
    )

    assert response.status_code == 200
    result = response.json()["data"]["results"][0]
    assert result["document_status"] == KnowledgeDocument.Status.NEEDS_REVIEW


@pytest.mark.django_db
def test_retrieval_verification_suppresses_red_flag_queries_from_hidoc(indexed_document):
    indexed_document.status = KnowledgeDocument.Status.READY
    indexed_document.save(update_fields=["status"])

    response = APIClient().get(
        reverse("knowledge-search-verify"),
        {"query": "소아 호흡곤란 청색증 응급", "source": "hidoc", "department_code": "PD000"},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert "answer" not in body
    assert body["results"] == []
    assert "red_flag_query" in body["safety_flags"]
    assert body["source_status"] == "retrieval_suppressed"
    assert body["llm_executed"] is False
    assert body["graph_executed"] is False
