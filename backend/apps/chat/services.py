from django.contrib.auth.models import AnonymousUser

from apps.chat.models import ChatMessage, ChatSession
from apps.loggingx.models import ChatLog


NO_KNOWLEDGE_ANSWER = (
    "No approved medical knowledge documents are indexed yet, so I cannot provide a "
    "source-grounded clinical answer. Please index approved clinical content before using "
    "Doctor Chat for medical knowledge retrieval."
)
SAFETY_NOTICE = (
    "Doctor Chat supports clinician information retrieval and does not replace clinician judgment."
)


def create_no_knowledge_chat_response(*, message: str, user, session_id=None) -> dict[str, object]:
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
    assistant_message = ChatMessage.objects.create(
        session=session,
        user=authenticated_user,
        role=ChatMessage.Role.ASSISTANT,
        content=NO_KNOWLEDGE_ANSWER,
        message_type="no_knowledge",
        safety_flags=["no_indexed_documents", "rag_unavailable"],
        metadata={
            "citations": [],
            "source_status": "no_indexed_documents",
            "langgraph_executed": False,
        },
    )
    ChatLog.objects.create(
        session=session,
        message=assistant_message,
        user=authenticated_user,
        event="no_knowledge_response",
        safety_flags=assistant_message.safety_flags,
        metadata={
            "source_status": "no_indexed_documents",
            "user_message_id": str(user_message.id),
            "assistant_message_id": str(assistant_message.id),
        },
    )

    return {
        "session_id": str(session.id),
        "user_message_id": str(user_message.id),
        "assistant_message_id": str(assistant_message.id),
        "answer": NO_KNOWLEDGE_ANSWER,
        "safety_notice": SAFETY_NOTICE,
        "source_status": "no_indexed_documents",
        "citations": [],
        "safety_flags": assistant_message.safety_flags,
        "graph": {
            "executed": False,
            "version": None,
            "path": ["no_knowledge_placeholder"],
        },
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
