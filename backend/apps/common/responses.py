from typing import Any

from rest_framework.response import Response


def std_response(
    *,
    data: Any = None,
    error: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    status: int = 200,
) -> Response:
    return Response(
        {
            "ok": error is None,
            "data": data,
            "error": error,
            "meta": meta or {},
        },
        status=status,
    )
