import uuid

from django.conf import settings
from django.db import models


def generate_request_id() -> str:
    return str(uuid.uuid4())


class ApiRequestLog(models.Model):
    request_id = models.CharField(max_length=64, default=generate_request_id, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="api_request_logs",
    )
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    status_code = models.PositiveSmallIntegerField()
    duration_ms = models.PositiveIntegerField(default=0)
    remote_addr = models.CharField(max_length=64, blank=True)
    user_agent = models.TextField(blank=True)
    request_summary = models.JSONField(default=dict, blank=True)
    response_summary = models.JSONField(default=dict, blank=True)
    error_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["path"]),
            models.Index(fields=["request_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.method} {self.path} {self.status_code}"


class LoginEventLog(models.Model):
    class EventType(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"
        LOGOUT = "logout", "Logout"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="login_event_logs",
    )
    username = models.CharField(max_length=150, blank=True)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    remote_addr = models.CharField(max_length=64, blank=True)
    user_agent = models.TextField(blank=True)
    error_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["created_at", "event_type"])]

    def __str__(self) -> str:
        return f"{self.username or 'unknown'} {self.event_type}"


class ServiceLog(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    service_name = models.CharField(max_length=120)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INFO)
    event = models.CharField(max_length=120)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    error_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["created_at", "service_name", "level"])]

    def __str__(self) -> str:
        return f"{self.service_name}:{self.event}"


class ChatLog(models.Model):
    session = models.ForeignKey(
        "chat.ChatSession",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="logs",
    )
    message = models.ForeignKey(
        "chat.ChatMessage",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="chat_logs",
    )
    event = models.CharField(max_length=120)
    safety_flags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    error_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["created_at", "event"])]

    def __str__(self) -> str:
        return self.event
