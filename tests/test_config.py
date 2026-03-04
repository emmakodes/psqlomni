from argparse import Namespace

from psqlomni import config as cfg


def _args(**overrides):
    base = {
        "host": None,
        "port": None,
        "username": None,
        "dbname": None,
        "password": None,
        "db_uri": None,
        "db_dialect": None,
    }
    base.update(overrides)
    return Namespace(**base)


def test_normalize_model_provider_aliases():
    assert cfg.normalize_model_provider("google") == "google_gemini"
    assert cfg.normalize_model_provider("google-genai") == "google_gemini"
    assert cfg.normalize_model_provider("OPENAI") == "openai"
    assert cfg.normalize_model_provider("unknown-provider") == "openai"
    assert cfg.normalize_model_provider(None) == "openai"


def test_build_structured_db_uri_sqlite_variants():
    assert cfg._build_structured_db_uri("sqlite", "", ":memory:", "", None, 0) == "sqlite:///:memory:"
    assert cfg._build_structured_db_uri("sqlite", "", "/tmp/app.db", "", None, 0) == "sqlite:////tmp/app.db"
    assert cfg._build_structured_db_uri("sqlite", "", "local.db", "", None, 0) == "sqlite:///local.db"


def test_build_structured_db_uri_non_sqlite_quotes_credentials():
    uri = cfg._build_structured_db_uri(
        db_dialect="postgresql",
        host="localhost",
        dbname="db name",
        user="alice+ops",
        password="p@ss word",
        port=5432,
    )
    assert uri == "postgresql://alice%2Bops:p%40ss+word@localhost:5432/db+name"


def test_port_and_password_modes():
    assert cfg._password_mode(None) == "missing"
    assert cfg._password_mode("") == "blank"
    assert cfg._password_mode("secret") == "set"
    assert cfg._port_mode(5432, "postgresql") == "default(5432)"
    assert cfg._port_mode(6543, "postgresql") == "custom(6543)"


def test_resolve_app_config_uses_env_and_writes_file(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "psqlomni.json")
    monkeypatch.setattr(cfg, "_validate_connection", lambda _: None)
    monkeypatch.setattr(cfg, "prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("prompt not expected")))

    monkeypatch.setenv("DBHOST", "localhost")
    monkeypatch.setenv("DBNAME", "analytics")
    monkeypatch.setenv("DBUSER", "service")
    monkeypatch.setenv("DBPASSWORD", "")
    monkeypatch.setenv("DBPORT", "5433")
    monkeypatch.setenv("MODEL_PROVIDER", "google")
    monkeypatch.setenv("GOOGLE_API_KEY", "gk_test")
    monkeypatch.setenv("MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("SAMPLE_ROWS_IN_TABLE_INFO", "5")

    app = cfg.resolve_app_config(_args())

    assert app.db_host == "localhost"
    assert app.db_name == "analytics"
    assert app.db_user == "service"
    assert app.db_port == 5433
    assert app.db_password == ""
    assert app.db_password_mode == "blank"
    assert app.model_provider == "google_gemini"
    assert app.model == "gemini-2.5-flash"
    assert app.sample_rows_in_table_info == 5
    assert app.db_host_source == "env"
    assert app.db_port_source == "env"
    assert app.db_name_source == "env"
    assert app.db_user_source == "env"
    assert app.db_password_source == "env"


def test_resolve_app_config_db_uri_from_cli(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "psqlomni.json")
    monkeypatch.setattr(cfg, "_validate_connection", lambda _: None)
    monkeypatch.setattr(cfg, "prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("prompt not expected")))

    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "ok_test")
    monkeypatch.setenv("MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("SAMPLE_ROWS_IN_TABLE_INFO", "3")

    app = cfg.resolve_app_config(_args(db_uri="sqlite:///:memory:"))

    assert app.db_uri == "sqlite:///:memory:"
    assert app.db_uri_source == "cli"
    assert app.db_dialect == "sqlite"


def test_save_model_config_updates_existing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "psqlomni.json")
    cfg.CONFIG_FILE.write_text(
        '{"DBHOST":"db.internal","DBNAME":"analytics","model_provider":"openai","model":"gpt-4.1-mini"}',
        encoding="utf-8",
    )
    app = cfg.AppConfig(
        db_uri=None,
        db_dialect="postgresql",
        db_host="db.internal",
        db_port=5432,
        db_name="analytics",
        db_user="service",
        db_password="secret",
        model_provider="google_gemini",
        openai_api_key=None,
        anthropic_api_key=None,
        google_api_key="gk_test",
        ollama_base_url=cfg.DEFAULT_OLLAMA_BASE_URL,
        model="gemini-2.5-flash",
        sample_rows_in_table_info=3,
        db_host_source="saved",
        db_port_source="default",
        db_name_source="saved",
        db_user_source="saved",
        db_password_source="saved",
        db_uri_source="missing",
        db_port_mode="default(5432)",
        db_password_mode="set",
    )

    cfg.save_model_config(app)
    payload = cfg._load_config_file()
    assert payload["DBHOST"] == "db.internal"
    assert payload["DBNAME"] == "analytics"
    assert payload["model_provider"] == "google_gemini"
    assert payload["model"] == "gemini-2.5-flash"
    assert payload["GOOGLE_API_KEY"] == "gk_test"
