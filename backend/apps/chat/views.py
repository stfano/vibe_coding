from django.core.exceptions import ObjectDoesNotExist
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from apps.chat.serializers import ChatMessageRequestSerializer
from apps.chat.services import create_chat_response
from apps.common.responses import std_response


@api_view(["POST"])
@permission_classes([AllowAny])
def create_chat_message(request):
    serializer = ChatMessageRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return std_response(
            error={
                "code": "invalid_chat_request",
                "message": "Chat message request is invalid.",
                "details": serializer.errors,
            },
            status=400,
        )

    try:
        payload = create_chat_response(
            message=serializer.validated_data["message"],
            user=request.user,
            session_id=serializer.validated_data.get("session_id"),
        )
    except ObjectDoesNotExist:
        return std_response(
            error={"code": "session_not_found", "message": "Chat session was not found."},
            status=404,
        )

    return std_response(
        data=payload,
        meta={"request_id": getattr(request, "doctor_chat_request_id", None)},
    )
