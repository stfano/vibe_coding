from __future__ import annotations

from django.http import Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from apps.common.responses import std_response
from apps.evaluation.services import (
    get_evaluation_run_detail,
    list_evaluation_datasets,
    list_evaluation_runs,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def evaluation_dataset_list(request):
    return std_response(
        data=list_evaluation_datasets(),
        meta={"request_id": getattr(request, "doctor_chat_request_id", None)},
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def evaluation_run_list(request):
    return std_response(
        data=list_evaluation_runs(),
        meta={"request_id": getattr(request, "doctor_chat_request_id", None)},
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def evaluation_run_detail(request, run_id: int):
    try:
        data = get_evaluation_run_detail(run_id)
    except Http404:
        return std_response(
            error={"code": "evaluation_run_not_found", "message": "Evaluation run was not found."},
            status=404,
        )
    return std_response(data=data, meta={"request_id": getattr(request, "doctor_chat_request_id", None)})
