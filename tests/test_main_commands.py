from types import SimpleNamespace

from psqlomni import __main__ as main_mod
from psqlomni.config import AppConfig
from psqlomni.__main__ import PSqlomni


class FakeRenderer:
    def __init__(self, mode="verbose"):
        self.mode = mode

    def set_mode(self, mode: str) -> None:
        self.mode = mode


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


def _app() -> PSqlomni:
    app = PSqlomni.__new__(PSqlomni)
    app.config = _config()
    app.db = object()
    app.llm = object()
    app.tools = {}
    app.graph = object()
    app.renderer = FakeRenderer(mode="verbose")
    app.thread_id = "thread-1"
    app.known_thread_ids = {"thread-1"}
    return app


def test_handle_mode_switch_and_invalid_mode(capsys):
    app = _app()

    handled = app._handle_slash_or_legacy_command("/mode normal")
    assert handled is True
    assert app.renderer.mode == "normal"
    assert "Output mode set to: normal" in capsys.readouterr().out

    handled_invalid = app._handle_slash_or_legacy_command("/mode bad")
    assert handled_invalid is True
    assert "Invalid mode. Use: /mode normal|verbose" in capsys.readouterr().out


def test_handle_provider_info_and_unsupported_provider(capsys):
    app = _app()

    assert app._handle_slash_or_legacy_command("/provider") is True
    output = capsys.readouterr().out
    assert "Current provider: openai" in output

    assert app._handle_slash_or_legacy_command("/provider not-real") is True
    assert "Unsupported provider" in capsys.readouterr().out


def test_handle_valid_provider_switch(monkeypatch, capsys):
    app = _app()
    app.config.openai_api_key = "ok_test"
    app.config.google_api_key = "gk_test"
    saved_configs = []

    monkeypatch.setattr(app, "_rebuild_model_runtime", lambda: None)
    monkeypatch.setattr(app, "_pick_model_interactive", lambda: None)
    monkeypatch.setattr(main_mod, "save_model_config", lambda config: saved_configs.append(config))

    assert app._handle_slash_or_legacy_command("/provider google") is True
    assert app.config.model_provider == "google_gemini"
    assert app.config.model == main_mod.DEFAULT_MODELS_BY_PROVIDER["google_gemini"]
    assert saved_configs == [app.config]
    output = capsys.readouterr().out
    assert "Provider set for this session: google_gemini" in output


def test_handle_model_switch_persists(monkeypatch, capsys):
    app = _app()
    saved_configs = []

    monkeypatch.setattr(app, "_rebuild_model_runtime", lambda: None)
    monkeypatch.setattr(main_mod, "save_model_config", lambda config: saved_configs.append(config))

    assert app._handle_slash_or_legacy_command("/model gpt-4.1") is True
    assert app.config.model == "gpt-4.1"
    assert saved_configs == [app.config]
    assert "Model set for this session: gpt-4.1" in capsys.readouterr().out


def test_handle_connection_new_resume_and_exit(monkeypatch, capsys):
    app = _app()
    monkeypatch.setattr(main_mod, "get_version", lambda: "0.1.1-test")
    monkeypatch.setattr(main_mod, "uuid4", lambda: "thread-2")

    assert app._handle_slash_or_legacy_command("/connection") is True
    connection_output = capsys.readouterr().out
    assert "Dialect: postgresql" in connection_output
    assert "Version: 0.1.1-test" in connection_output

    assert app._handle_slash_or_legacy_command("/new") is True
    assert app.thread_id == "thread-2"
    assert "thread-2" in app.known_thread_ids

    assert app._handle_slash_or_legacy_command("/resume unknown-thread") is True
    assert "Unknown thread id for this session." in capsys.readouterr().out

    assert app._handle_slash_or_legacy_command("/resume thread-1") is True
    assert app.thread_id == "thread-1"
    assert "Resumed thread: thread-1" in capsys.readouterr().out

    assert app._handle_slash_or_legacy_command("/exit") is False


def test_handle_disconnect_and_connect_delegate(monkeypatch):
    app = _app()
    calls = SimpleNamespace(disconnect=0, connect=0)

    monkeypatch.setattr(app, "_disconnect_database", lambda: setattr(calls, "disconnect", calls.disconnect + 1))
    monkeypatch.setattr(app, "_connect_database_interactive", lambda: setattr(calls, "connect", calls.connect + 1))

    assert app._handle_slash_or_legacy_command("/disconnect") is True
    assert app._handle_slash_or_legacy_command("/connect") is True
    assert calls.disconnect == 1
    assert calls.connect == 1


def test_prompt_query_decision_paths(monkeypatch, capsys):
    app = _app()
    app.renderer = SimpleNamespace(print_approval_prompt=lambda **kwargs: None)

    prompts = iter(["bad", "a"])
    monkeypatch.setattr(main_mod, "prompt", lambda *_args, **_kwargs: next(prompts))
    decision = app._prompt_query_decision({"query": "SELECT 1", "is_mutating": False})
    assert decision == {"action": "accept"}
    assert "Invalid choice. Use a/e/f/c." in capsys.readouterr().out

    prompts = iter(["e", "SELECT 2"])
    monkeypatch.setattr(main_mod, "prompt", lambda *_args, **_kwargs: next(prompts))
    assert app._prompt_query_decision({"query": "SELECT 1", "is_mutating": False}) == {"action": "edit", "query": "SELECT 2"}

    prompts = iter(["f", "Need date range"])
    monkeypatch.setattr(main_mod, "prompt", lambda *_args, **_kwargs: next(prompts))
    assert app._prompt_query_decision({"query": "SELECT 1", "is_mutating": False}) == {
        "action": "feedback",
        "message": "Need date range",
    }

    prompts = iter(["c"])
    monkeypatch.setattr(main_mod, "prompt", lambda *_args, **_kwargs: next(prompts))
    assert app._prompt_query_decision({"query": "SELECT 1", "is_mutating": False}) == {"action": "cancel"}


def test_connect_database_interactive_uri_mode(monkeypatch, capsys):
    app = _app()
    app.thread_id = "thread-1"
    app.known_thread_ids = {"thread-1"}

    prompt_calls = []

    def fake_prompt(message, **kwargs):
        prompt_calls.append((message, kwargs))
        return "mysql://bob:topsecret@db.internal:3307/warehouse"

    db_calls = []
    run_calls = []

    class FakeDB:
        def run_no_throw(self, query):
            run_calls.append(query)

    def fake_build_sql_database(config):
        db_calls.append(config)
        return FakeDB()

    tools_calls = []

    def fake_build_sql_tools(db, llm):
        tools_calls.append((db, llm))
        return {"sql_query": object()}

    graph_calls = []

    def fake_build_sql_graph(llm, tools, db_dialect, db_name):
        graph_calls.append((llm, tools, db_dialect, db_name))
        return object()

    saved_configs = []
    monkeypatch.setattr(main_mod, "prompt", fake_prompt)
    monkeypatch.setattr(main_mod, "build_sql_database", fake_build_sql_database)
    monkeypatch.setattr(main_mod, "build_sql_tools", fake_build_sql_tools)
    monkeypatch.setattr(main_mod, "build_sql_graph", fake_build_sql_graph)
    monkeypatch.setattr(main_mod, "save_connection_config", lambda config: saved_configs.append(config))
    monkeypatch.setattr(main_mod, "uuid4", lambda: "thread-2")

    app._connect_database_interactive()

    assert len(prompt_calls) == 1
    assert prompt_calls[0][0].startswith("DB URI [")
    assert db_calls[0].db_uri == "mysql://bob:topsecret@db.internal:3307/warehouse"
    assert run_calls == ["SELECT 1"]
    assert app.config.db_dialect == "mysql"
    assert app.config.db_host == "db.internal"
    assert app.config.db_port == 3307
    assert app.config.db_name == "warehouse"
    assert app.config.db_user == "bob"
    assert app.config.db_password == "topsecret"
    assert app.config.db_uri_source == "prompt"
    assert app.config.db_port_mode == "custom(3307)"
    assert app.config.db_password_mode == "set"
    assert len(tools_calls) == 1
    assert len(graph_calls) == 1
    assert graph_calls[0][2] == "mysql"
    assert graph_calls[0][3] == "warehouse"
    assert saved_configs == [app.config]
    assert app.thread_id == "thread-2"
    assert "thread-2" in app.known_thread_ids

    output = capsys.readouterr().out
    assert "Connected to mysql://bob:topsecret@db.internal:3307/warehouse" in output
    assert "Started new thread: thread-2" in output


def test_connect_database_interactive_structured_mode(monkeypatch, capsys):
    app = _app()
    app.config.db_password = "existing-secret"
    app.config.db_password_source = "env"

    prompt_answers = iter(
        [
            "",
            "mysql",
            "db.prod",
            "events",
            "reporter",
            "3306",
            "",
        ]
    )
    prompt_calls = []

    def fake_prompt(message, **kwargs):
        prompt_calls.append((message, kwargs))
        return next(prompt_answers)

    db_calls = []
    run_calls = []

    class FakeDB:
        def run_no_throw(self, query):
            run_calls.append(query)

    def fake_build_sql_database(config):
        db_calls.append(config)
        return FakeDB()

    tools_calls = []

    def fake_build_sql_tools(db, llm):
        tools_calls.append((db, llm))
        return {"sql_query": object()}

    graph_calls = []

    def fake_build_sql_graph(llm, tools, db_dialect, db_name):
        graph_calls.append((llm, tools, db_dialect, db_name))
        return object()

    saved_configs = []
    monkeypatch.setattr(main_mod, "prompt", fake_prompt)
    monkeypatch.setattr(main_mod, "build_sql_database", fake_build_sql_database)
    monkeypatch.setattr(main_mod, "build_sql_tools", fake_build_sql_tools)
    monkeypatch.setattr(main_mod, "build_sql_graph", fake_build_sql_graph)
    monkeypatch.setattr(main_mod, "save_connection_config", lambda config: saved_configs.append(config))
    monkeypatch.setattr(main_mod, "uuid4", lambda: "thread-9")

    app._connect_database_interactive()

    assert len(prompt_calls) == 7
    assert prompt_calls[0][0].startswith("DB URI [")
    assert prompt_calls[-1][1]["is_password"] is True
    assert db_calls[0].db_uri is None
    assert db_calls[0].db_dialect == "mysql"
    assert db_calls[0].db_host == "db.prod"
    assert db_calls[0].db_name == "events"
    assert db_calls[0].db_user == "reporter"
    assert db_calls[0].db_port == 3306
    assert db_calls[0].db_password == "existing-secret"
    assert db_calls[0].db_password_source == "env"
    assert db_calls[0].db_port_mode == "default(3306)"
    assert run_calls == ["SELECT 1"]
    assert len(tools_calls) == 1
    assert len(graph_calls) == 1
    assert graph_calls[0][2] == "mysql"
    assert graph_calls[0][3] == "events"
    assert saved_configs == [app.config]
    assert app.thread_id == "thread-9"
    assert "thread-9" in app.known_thread_ids

    output = capsys.readouterr().out
    assert "Connected to mysql://db.prod:3306/events" in output
    assert "Started new thread: thread-9" in output
