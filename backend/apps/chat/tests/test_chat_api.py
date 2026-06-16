import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.chat.models import ChatMessage, ChatSession
from apps.loggingx.models import ApiRequestLog, ChatLog


@pytest.mark.django_db
def test_chat_endpoint_returns_safe_no_knowledge_response_and_persists_messages():
    response = APIClient().post(
        reverse("chat-message-list"),
        {"message": "What is the recommended treatment for synthetic condition?"},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["error"] is None
    assert body["data"]["source_status"] == "no_indexed_documents"
    assert body["data"]["citations"] == []
    assert body["data"]["graph"]["executed"] is False
    assert "approved medical knowledge documents are indexed" in body["data"]["answer"]
    assert "does not replace clinician judgment" in body["data"]["safety_notice"]

    session = ChatSession.objects.get(id=body["data"]["session_id"])
    messages = list(ChatMessage.objects.filter(session=session).order_by("created_at"))
    assert len(messages) == 2
    assert messages[0].role == ChatMessage.Role.USER
    assert messages[1].role == ChatMessage.Role.ASSISTANT
    assert messages[1].message_type == "no_knowledge"
    assert "no_indexed_documents" in messages[1].safety_flags
    assert ChatLog.objects.filter(session=session, event="no_knowledge_response").exists()


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
    assert body["data"]["source_status"] == "no_indexed_documents"
    assert body["data"]["citations"] == []
    assert body["data"]["graph"]["executed"] is False
    assert "approved medical knowledge documents are indexed" in body["data"]["answer"]
