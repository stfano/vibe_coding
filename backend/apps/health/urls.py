from django.urls import path

from apps.health.views import health


urlpatterns = [
    path("", health, name="health"),
]
