from django.contrib.auth.models import AnonymousUser

from apps.chat.models import ChatMessage, ChatSession
from apps.graph.router import run_chat_safety_graph
from apps.loggingx.models import ChatLog


SAFETY_NOTICE = (
    "Doctor Chat supports clinician information retrieval and does not replace clinician judgment."
)


def create_chat_response(*, message: str, user, session_id=None) -> dict[str, object]:
    authenticated_user = _authenticated_user_or_none(user)
    session = _get_or_create_session(
        message=message,
        user=authenticated_user,
        session_id=session_id,
    )
    user_message = ChatMessage.objects.create(
        session=session,
        user=authenticated_user,
        role=ChatMessage.Role.USER,
        content=message,
        message_type="user_input",
        metadata={"entrypoint": "non_streaming_chat_api"},
    )
    graph_result = run_chat_safety_graph(message=message)
    assistant_message = ChatMessage.objects.create(
        session=session,
        user=authenticated_user,
        role=ChatMessage.Role.ASSISTANT,
        content=graph_result["answer"],
        message_type=_message_type_for_source_status(graph_result["source_status"]),
        safety_flags=graph_result["safety_flags"],
        metadata={
            "citations": graph_result["citations"],
            "source_status": graph_result["source_status"],
            "graph": graph_result["graph"],
            "retrieved_chunks": graph_result["retrieved_chunks"],
            "llm_executed": graph_result["llm_executed"],
        },
    )
    session.metadata = {
        **session.metadata,
        "source_status": graph_result["source_status"],
        "graph_version": graph_result["graph"]["version"],
    }
    session.save(update_fields=["metadata", "updated_at"])
    ChatLog.objects.create(
        session=session,
        message=assistant_message,
        user=authenticated_user,
        event="graph_chat_response",
        safety_flags=assistant_message.safety_flags,
        metadata={
            "source_status": graph_result["source_status"],
            "user_message_id": str(user_message.id),
            "assistant_message_id": str(assistant_message.id),
            "graph": graph_result["graph"],
            "citations": graph_result["citations"],
            "retrieved_source_ids": graph_result["retrieved_source_ids"],
            "llm_executed": graph_result["llm_executed"],
        },
    )

    return {
        "session_id": str(session.id),
        "user_message_id": str(user_message.id),
        "assistant_message_id": str(assistant_message.id),
        "answer": graph_result["answer"],
        "safety_notice": SAFETY_NOTICE,
        "source_status": graph_result["source_status"],
        "citations": graph_result["citations"],
        "safety_flags": assistant_message.safety_flags,
        "graph": graph_result["graph"],
        "retrieved_source_ids": graph_result["retrieved_source_ids"],
        "llm_executed": graph_result["llm_executed"],
    }


def _get_or_create_session(*, message: str, user, session_id=None) -> ChatSession:
    if session_id:
        return ChatSession.objects.get(id=session_id)

    title = message.strip().replace("\n", " ")[:120] or "New clinical support chat"
    return ChatSession.objects.create(
        user=user,
        title=title,
        metadata={"source_status": "no_indexed_documents"},
    )


def _authenticated_user_or_none(user):
    if isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return None
    return user


def _message_type_for_source_status(source_status: str) -> str:
    if source_status == "retrieved":
        return "graph_retrieval_context"
    if source_status == "urgent_escalation":
        return "graph_urgent_escalation"
    if source_status == "low_confidence":
        return "graph_low_confidence"
    return "graph_no_source"
