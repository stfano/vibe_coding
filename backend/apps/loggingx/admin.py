from django.contrib import admin

from apps.loggingx.models import ApiRequestLog, ChatLog, LoginEventLog, ServiceLog


@admin.register(ApiRequestLog)
class ApiRequestLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "method", "path", "status_code", "duration_ms", "user")
    list_filter = ("method", "status_code", "created_at")
    search_fields = ("request_id", "path", "user__username")
    readonly_fields = (
        "request_id",
        "user",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "remote_addr",
        "user_agent",
        "request_summary",
        "response_summary",
        "error_summary",
        "created_at",
    )


@admin.register(LoginEventLog)
class LoginEventLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "username", "event_type", "user")
    list_filter = ("event_type", "created_at")
    search_fields = ("username", "user__username")


@admin.register(ServiceLog)
class ServiceLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "service_name", "level", "event")
    list_filter = ("level", "service_name", "created_at")
    search_fields = ("service_name", "event", "message")


@admin.register(ChatLog)
class ChatLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "session", "message", "user")
    list_filter = ("event", "created_at")
    search_fields = ("event", "session__id", "message__id", "user__username")
