from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from apps.common.responses import std_response
from apps.health.services import get_health_payload


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return std_response(
        data=get_health_payload(),
        meta={"version": settings.SERVICE_VERSION},
    )
