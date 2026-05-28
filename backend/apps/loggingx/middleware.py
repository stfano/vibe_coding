from time import perf_counter
from uuid import uuid4

from apps.loggingx.models import ApiRequestLog


class ApiRequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.doctor_chat_request_id = request_id
        started_at = perf_counter()

        try:
            response = self.get_response(request)
        except Exception as exc:
            if request.path.startswith("/api/"):
                duration_ms = int((perf_counter() - started_at) * 1000)
                self._record_log(request, request_id, 500, duration_ms, exc.__class__.__name__)
            raise

        if request.path.startswith("/api/"):
            duration_ms = int((perf_counter() - started_at) * 1000)
            status_code = getattr(response, "status_code", 500)
            self._record_log(request, request_id, status_code, duration_ms, "")
            response["X-Request-ID"] = request_id

        return response

    def _record_log(self, request, request_id: str, status_code: int, duration_ms: int, error_summary: str) -> None:
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            user = None

        ApiRequestLog.objects.create(
            request_id=request_id,
            user=user,
            method=request.method,
            path=request.path,
            status_code=status_code,
            duration_ms=duration_ms,
            remote_addr=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request_summary={
                "content_type": request.META.get("CONTENT_TYPE", ""),
                "query_keys": sorted(request.GET.keys()),
                "body_size": int(request.META.get("CONTENT_LENGTH") or 0),
            },
            response_summary={"status_code": status_code},
            error_summary=error_summary,
        )
