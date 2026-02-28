import pytest

from psqlomni.config import AppConfig
from psqlomni.llm import build_llm


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
        openai_api_key="ok_test",
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


def test_build_llm_rejects_unsupported_provider():
    config = _config(model_provider="unsupported")
    with pytest.raises(ValueError, match="Unsupported model provider"):
        build_llm(config)
