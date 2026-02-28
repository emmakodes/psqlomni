from psqlomni.config import AppConfig
from psqlomni.db import build_connection_string


def _config(**overrides) -> AppConfig:
    base = dict(
        db_uri=None,
        db_dialect="postgresql",
        db_host="localhost",
        db_port=5432,
        db_name="analytics",
        db_user="alice",
        db_password="secret",
        model_provider="openai",
        openai_api_key=None,
        anthropic_api_key=None,
        google_api_key=None,
        ollama_base_url="http://localhost:11434",
        model="gpt-4.1-mini",
        sample_rows_in_table_info=3,
        db_host_source="env",
        db_port_source="env",
        db_name_source="env",
        db_user_source="env",
        db_password_source="env",
        db_uri_source="missing",
        db_port_mode="default(5432)",
        db_password_mode="set",
    )
    base.update(overrides)
    return AppConfig(**base)


def test_build_connection_string_prefers_db_uri():
    config = _config(db_uri="postgresql://x:y@z:5432/mydb")
    assert build_connection_string(config) == "postgresql://x:y@z:5432/mydb"


def test_build_connection_string_sqlite_variants():
    memory = _config(db_dialect="sqlite", db_name=":memory:")
    absolute = _config(db_dialect="sqlite", db_name="/tmp/app.db")
    relative = _config(db_dialect="sqlite", db_name="local.db")
    assert build_connection_string(memory) == "sqlite:///:memory:"
    assert build_connection_string(absolute) == "sqlite:////tmp/app.db"
    assert build_connection_string(relative) == "sqlite:///local.db"


def test_build_connection_string_quotes_and_handles_blank_password():
    no_password = _config(db_user="alice+ops", db_name="db name", db_password="")
    with_password = _config(db_user="alice+ops", db_name="db name", db_password="p@ss word")
    assert build_connection_string(no_password) == "postgresql://alice%2Bops@localhost:5432/db+name"
    assert build_connection_string(with_password) == "postgresql://alice%2Bops:p%40ss+word@localhost:5432/db+name"
