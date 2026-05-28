import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    if value is None:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def database_from_url(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("DATABASE_URL must use postgres:// or postgresql://")

    options = {}
    query = parse_qs(parsed.query)
    if sslmode := query.get("sslmode", [None])[0]:
        options["sslmode"] = sslmode

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/") or "postgres"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or 5432),
        "CONN_MAX_AGE": int(env("DATABASE_CONN_MAX_AGE", "60")),
        "OPTIONS": options,
    }


SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)
DEBUG = env_bool("DJANGO_DEBUG", False)
SERVICE_VERSION = env("SERVICE_VERSION", "0.1.0")

ALLOWED_HOSTS = [
    host.strip()
    for host in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.common",
    "apps.health",
    "apps.authx",
    "apps.loggingx",
    "apps.chat",
    "apps.knowledge",
    "apps.rag",
    "apps.graph",
    "apps.evaluation",
    "apps.adminx",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.loggingx.middleware.ApiRequestLogMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = env("DATABASE_URL", "") or env("SUPABASE_DATABASE_URL", "")

if DATABASE_URL:
    DATABASES = {"default": database_from_url(DATABASE_URL)}
elif env("POSTGRES_HOST", ""):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", "doctor_chat"),
            "USER": env("POSTGRES_USER", "doctor_chat"),
            "PASSWORD": env("POSTGRES_PASSWORD", required=True),
            "HOST": env("POSTGRES_HOST", "postgres"),
            "PORT": env("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in env("DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
QDRANT_URL = env("QDRANT_URL", "http://localhost:6333")
MINIO_ENDPOINT = env("MINIO_ENDPOINT", "localhost:9000")
MINIO_BUCKET = env("MINIO_BUCKET", "doctor-chat-documents")
EMBEDDING_SERVICE_URL = env("EMBEDDING_SERVICE_URL", "http://localhost:8080")
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", "http://localhost:11434")
