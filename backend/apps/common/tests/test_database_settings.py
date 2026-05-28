from config.settings import database_from_url


def test_database_from_supabase_url_parses_sslmode():
    config = database_from_url(
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres?sslmode=require"
    )

    assert config["ENGINE"] == "django.db.backends.postgresql"
    assert config["NAME"] == "postgres"
    assert config["USER"] == "postgres"
    assert config["PASSWORD"] == "secret"
    assert config["HOST"] == "db.example.supabase.co"
    assert config["PORT"] == "5432"
    assert config["OPTIONS"] == {"sslmode": "require"}


def test_database_from_url_decodes_credentials():
    config = database_from_url("postgres://user%40tenant:p%40ss@localhost:6543/app")

    assert config["NAME"] == "app"
    assert config["USER"] == "user@tenant"
    assert config["PASSWORD"] == "p@ss"
    assert config["PORT"] == "6543"
