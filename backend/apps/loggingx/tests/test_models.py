import pytest
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.test import RequestFactory

from apps.loggingx.models import ApiRequestLog, LoginEventLog, ServiceLog


@pytest.mark.django_db
def test_log_models_can_store_operational_events():
    api_log = ApiRequestLog.objects.create(
        method="GET",
        path="/api/health/",
        status_code=200,
        duration_ms=7,
    )
    login_log = LoginEventLog.objects.create(username="clinician", event_type="success")
    service_log = ServiceLog.objects.create(
        service_name="backend",
        level="info",
        event="startup_check",
        message="Service check recorded.",
    )

    assert api_log.path == "/api/health/"
    assert login_log.event_type == "success"
    assert service_log.metadata == {}


@pytest.mark.django_db
def test_login_signal_records_login_event():
    user = User.objects.create_user(username="clinician", password="test-password")
    request = RequestFactory().post(
        "/admin/login/",
        REMOTE_ADDR="127.0.0.1",
        HTTP_USER_AGENT="pytest",
    )

    user_logged_in.send(sender=User, request=request, user=user)

    login_log = LoginEventLog.objects.get(username="clinician")
    assert login_log.user == user
    assert login_log.event_type == LoginEventLog.EventType.SUCCESS
    assert login_log.remote_addr == "127.0.0.1"
