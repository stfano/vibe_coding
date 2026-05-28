from django.apps import AppConfig


class LoggingxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.loggingx"

    def ready(self) -> None:
        import apps.loggingx.signals  # noqa: F401
