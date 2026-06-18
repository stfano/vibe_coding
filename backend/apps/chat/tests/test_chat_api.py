import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.chat.models import ChatMessage, ChatSession
from apps.knowledge.indexing import ExternalQnaIndexer
from apps.knowledge.models import ExternalQnaRecord, KnowledgeDocument
from apps.loggingx.models import ApiRequestLog, ChatLog
from apps.rag.embeddings import DeterministicEmbeddingAdapter


@pytest.fixture
def indexed_qna_document() -> KnowledgeDocument:
    record = ExternalQnaRecord.objects.create(
        source="hidoc",
        external_id="hidoc:CHAT100:A100",
        content_hash="chat-hash-1",
        department="소아청소년과",
        source_department_code="PD000",
        source_question_id="CHAT100",
        source_answer_id="A100",
        source_url="https://www.hidoc.co.kr/healthqna/view/CHAT100",
        list_page=1,
        question_title="아기 고환 물집",
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
def test_chat_endpoint_runs_graph_and_returns_safe_no_source_fallback():
    response = APIClient().post(
        reverse("chat-message-list"),
        {"message": "What is the recommended treatment for synthetic condition?"},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["error"] is None
    assert body["data"]["source_status"] == "no_matching_ready_documents"
    assert body["data"]["citations"] == []
    assert body["data"]["graph"]["executed"] is True
    assert body["data"]["llm_executed"] is False
    assert body["data"]["graph"]["path"] == [
        "validate_input",
        "detect_red_flags",
        "retrieve_ready_documents",
        "decide_source_status",
        "format_response",
        "persist_metadata",
    ]
    assert body["data"]["graph"]["retrieved_source_ids"] == []
    assert body["data"]["graph"]["model_name"] is None
    assert body["data"]["graph"]["prompt_version"] is None
    assert "approved medical knowledge documents are indexed" in body["data"]["answer"]
    assert "does not replace clinician judgment" in body["data"]["safety_notice"]

    session = ChatSession.objects.get(id=body["data"]["session_id"])
    messages = list(ChatMessage.objects.filter(session=session).order_by("created_at"))
    assert len(messages) == 2
    assert messages[0].role == ChatMessage.Role.USER
    assert messages[1].role == ChatMessage.Role.ASSISTANT
    assert messages[1].message_type == "graph_no_source"
    assert "no_ready_documents" in messages[1].safety_flags
    assert messages[1].metadata["graph"]["executed"] is True
    assert ChatLog.objects.filter(session=session, event="graph_chat_response").exists()


@pytest.mark.django_db
def test_chat_endpoint_records_api_request_log():
    response = APIClient().post(
        reverse("chat-message-list"),
        {"message": "Can you answer from local indexed documents?"},
        format="json",
    )

    assert response.status_code == 200
    api_log = ApiRequestLog.objects.get(path="/api/chat/messages/")
    assert api_log.method == "POST"
    assert api_log.status_code == 200
    assert api_log.request_summary["body_size"] > 0
    assert "message" not in api_log.request_summary


@pytest.mark.django_db
def test_chat_endpoint_does_not_answer_red_flag_query_from_hidoc():
    response = APIClient().post(
        reverse("chat-message-list"),
        {"message": "소아가 호흡곤란과 청색증이 있습니다. 하이닥 자료로 답해줘."},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["source_status"] == "urgent_escalation"
    assert body["data"]["citations"] == []
    assert body["data"]["graph"]["executed"] is True
    assert body["data"]["llm_executed"] is False
    assert body["data"]["graph"]["path"] == [
        "validate_input",
        "detect_red_flags",
        "decide_source_status",
        "format_response",
        "persist_metadata",
    ]
    assert "red_flag_query" in body["data"]["safety_flags"]
    assert "urgent" in body["data"]["answer"].lower()


@pytest.mark.django_db
def test_chat_endpoint_excludes_needs_review_documents(indexed_qna_document):
    response = APIClient().post(
        reverse("chat-message-list"),
        {"message": "아기 고환 물집 아기띠"},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert indexed_qna_document.status == KnowledgeDocument.Status.NEEDS_REVIEW
    assert body["source_status"] == "no_matching_ready_documents"
    assert body["llm_executed"] is False
    assert body["citations"] == []
    assert body["graph"]["retrieved_source_ids"] == []


@pytest.mark.django_db
def test_chat_endpoint_retrieves_ready_document_with_citation_metadata(indexed_qna_document):
    indexed_qna_document.status = KnowledgeDocument.Status.READY
    indexed_qna_document.save(update_fields=["status"])

    response = APIClient().post(
        reverse("chat-message-list"),
        {"message": "아기 고환 물집 아기띠"},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["source_status"] == "retrieved"
    assert body["llm_executed"] is True
    assert body["citations"][0]["external_question_id"] == "CHAT100"
    assert body["citations"][0]["external_answer_id"] == "A100"
    assert body["graph"]["executed"] is True
    assert body["graph"]["model_name"]
    assert body["graph"]["prompt_version"]
    assert body["graph"]["retrieved_source_ids"] == [indexed_qna_document.id]
    assert "retrieved_context_available" in body["safety_flags"]
    assert "CHAT100" in body["answer"]
