from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/chat/", include("apps.chat.urls")),
    path("api/evaluation/", include("apps.evaluation.urls")),
    path("api/health/", include("apps.health.urls")),
    path("api/knowledge/", include("apps.knowledge.urls")),
]
