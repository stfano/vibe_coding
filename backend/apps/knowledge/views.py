from __future__ import annotations

from django.http import Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from apps.common.responses import std_response
from apps.knowledge.serializers import (
    KnowledgeDocumentFilterSerializer,
    KnowledgeDocumentStatusUpdateSerializer,
    KnowledgeSearchVerificationSerializer,
)
from apps.knowledge.services import (
    get_knowledge_document_detail,
    list_knowledge_documents,
    update_knowledge_document_status,
    verify_knowledge_search,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def knowledge_document_list(request):
    serializer = KnowledgeDocumentFilterSerializer(data=request.query_params)
    if not serializer.is_valid():
        return std_response(
            error={
                "code": "invalid_document_filters",
                "message": "Knowledge document filters are invalid.",
                "details": serializer.errors,
            },
            status=400,
        )
    return std_response(
        data=list_knowledge_documents(serializer.validated_data),
        meta={"request_id": getattr(request, "doctor_chat_request_id", None)},
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def knowledge_document_detail(request, document_id: int):
    try:
        data = get_knowledge_document_detail(document_id)
    except Http404:
        return std_response(
            error={"code": "document_not_found", "message": "Knowledge document was not found."},
            status=404,
        )
    return std_response(data=data, meta={"request_id": getattr(request, "doctor_chat_request_id", None)})


@api_view(["PATCH"])
@permission_classes([AllowAny])
def knowledge_document_status(request, document_id: int):
    serializer = KnowledgeDocumentStatusUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return std_response(
            error={
                "code": "invalid_document_status",
                "message": "Knowledge document status is invalid.",
                "details": serializer.errors,
            },
            status=400,
        )
    try:
        data = update_knowledge_document_status(document_id, status=serializer.validated_data["status"])
    except Http404:
        return std_response(
            error={"code": "document_not_found", "message": "Knowledge document was not found."},
            status=404,
        )
    return std_response(data=data, meta={"request_id": getattr(request, "doctor_chat_request_id", None)})


@api_view(["GET"])
@permission_classes([AllowAny])
def knowledge_search_verify(request):
    serializer = KnowledgeSearchVerificationSerializer(data=request.query_params)
    if not serializer.is_valid():
        return std_response(
            error={
                "code": "invalid_search_verification_request",
                "message": "Knowledge search verification request is invalid.",
                "details": serializer.errors,
            },
            status=400,
        )
    data = verify_knowledge_search(
        query=serializer.validated_data["query"],
        top_k=serializer.validated_data["top_k"],
        source=serializer.validated_data.get("source") or None,
        department_code=serializer.validated_data.get("department_code") or None,
        include_needs_review=serializer.validated_data["include_needs_review"],
    )
    return std_response(data=data, meta={"request_id": getattr(request, "doctor_chat_request_id", None)})
