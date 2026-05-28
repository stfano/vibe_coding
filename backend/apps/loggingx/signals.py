from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from apps.loggingx.models import LoginEventLog


@receiver(user_logged_in)
def record_login_success(sender, request, user, **kwargs) -> None:
    LoginEventLog.objects.create(
        user=user,
        username=user.get_username(),
        event_type=LoginEventLog.EventType.SUCCESS,
        remote_addr=_remote_addr(request),
        user_agent=_user_agent(request),
    )


@receiver(user_logged_out)
def record_logout(sender, request, user, **kwargs) -> None:
    LoginEventLog.objects.create(
        user=user if user and user.is_authenticated else None,
        username=user.get_username() if user else "",
        event_type=LoginEventLog.EventType.LOGOUT,
        remote_addr=_remote_addr(request),
        user_agent=_user_agent(request),
    )


@receiver(user_login_failed)
def record_login_failure(sender, credentials, request, **kwargs) -> None:
    LoginEventLog.objects.create(
        username=str(credentials.get("username", "")),
        event_type=LoginEventLog.EventType.FAILURE,
        remote_addr=_remote_addr(request),
        user_agent=_user_agent(request),
        error_summary="login_failed",
    )


def _remote_addr(request) -> str:
    if request is None:
        return ""
    return request.META.get("REMOTE_ADDR", "")


def _user_agent(request) -> str:
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")
