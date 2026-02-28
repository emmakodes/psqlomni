import argparse
import importlib.metadata
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import toml
from prompt_toolkit import prompt
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import make_url

DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_DB_PORT = 5432
DEFAULT_DB_DIALECT = "postgresql"
CONFIG_FILE = Path(os.path.expanduser("~/.psqlomni"))
_MISSING = object()
PROVIDER_ALIASES = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google_gemini",
    "gemini": "google_gemini",
    "google_genai": "google_gemini",
    "google-genai": "google_gemini",
    "google_gemini": "google_gemini",
    "ollama": "ollama",
}
DEFAULT_MODELS_BY_PROVIDER = {
    "openai": DEFAULT_MODEL,
    "anthropic": "claude-sonnet-4-5-20250929",
    "google_gemini": "gemini-2.5-flash",
    "ollama": "qwen3-coder-next",
}
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_DB_PORT_BY_DIALECT = {
    "postgresql": 5432,
    "mysql": 3306,
    "mariadb": 3306,
    "mssql": 1433,
    "oracle": 1521,
}
MODEL_CATALOG_BY_PROVIDER = {
    "openai": [
        "gpt-5.2",
        "gpt-5.2-pro",
        "gpt-5.2-codex",
        "gpt-5.2-chat-latest",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
    ],
    "anthropic": [
        "claude-opus-4-5-20251101",
        "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
        "claude-opus-4-1-20250805",
        "claude-sonnet-4-20250514",
        "claude-3-7-sonnet-latest",
        "claude-3-5-haiku-latest",
    ],
    "google_gemini": [
        "gemini-3-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
    ],
    "ollama": [
        "lfm2",
        "qwen3-coder-next",
        "qwen3.5",
        "glm-ocr",
        "lfm2.5-thinking",
        "glm-4.7-flash",
        "qwen3-vl",
        "ministral-3",
        "granite4",
        "rnj-1",
        "qwen3-next",
        "nemotron-3-nano",
        "devstral-small-2",
        "olmo-3.1",
        "devstral-2",
        "functiongemma",
        "gpt-oss-safeguard",
        "qwen3",
        "gpt-oss",
        "qwen3-coder",
    ],
}


@dataclass
class AppConfig:
    db_uri: str | None
    db_dialect: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str | None
    model_provider: str
    openai_api_key: str | None
    anthropic_api_key: str | None
    google_api_key: str | None
    ollama_base_url: str
    model: str
    sample_rows_in_table_info: int
    db_host_source: str
    db_port_source: str
    db_name_source: str
    db_user_source: str
    db_password_source: str
    db_uri_source: str
    db_port_mode: str
    db_password_mode: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-help", "--help", action="help", default=argparse.SUPPRESS, help="Show this help message and exit")
    parser.add_argument("-h", "--host", type=str, required=False)
    parser.add_argument("-p", "--port", type=int, required=False)
    parser.add_argument("-U", "--username", type=str, required=False)
    parser.add_argument("-d", "--dbname", type=str, required=False)
    parser.add_argument("--password", type=str, required=False)
    parser.add_argument("--db-uri", type=str, required=False)
    parser.add_argument("--db-dialect", type=str, required=False)
    return parser.parse_args()


def _load_config_file() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open("r", encoding="utf-8") as handle:
        return json.loads(handle.read())


def _save_config_file(config: dict[str, Any]) -> None:
    serializable = dict(config)
    for key, value in serializable.items():
        if isinstance(value, datetime):
            serializable[key] = value.isoformat()
    with CONFIG_FILE.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(serializable))


def _resolve_value(
    *,
    config: dict[str, Any],
    config_key: str,
    cli_value: Any,
    env_key: str,
    default: Any = _MISSING,
) -> tuple[Any, str]:
    if cli_value is not None:
        return cli_value, "cli"

    env_value = os.environ.get(env_key)
    if env_value is not None:
        return env_value, "env"

    if config_key in config:
        return config.get(config_key), "saved"

    if default is not _MISSING:
        return default, "default"

    return None, "missing"


def _password_mode(password: str | None) -> str:
    if password is None:
        return "missing"
    if password == "":
        return "blank"
    return "set"


def _port_mode(port: int, dialect: str) -> str:
    default_port = _default_port_for_dialect(dialect)
    if int(port) == default_port:
        return f"default({default_port})"
    return f"custom({port})"


def _default_port_for_dialect(dialect: str) -> int:
    return DEFAULT_DB_PORT_BY_DIALECT.get(dialect.lower(), DEFAULT_DB_PORT)


def _build_structured_db_uri(
    db_dialect: str,
    host: str,
    dbname: str,
    user: str,
    password: str | None,
    port: int,
) -> str:
    normalized = (db_dialect or DEFAULT_DB_DIALECT).strip().lower()
    if normalized.startswith("sqlite"):
        if dbname in {"", ":memory:"}:
            return "sqlite:///:memory:"
        if dbname.startswith("/"):
            return f"sqlite:////{dbname.lstrip('/')}"
        return f"sqlite:///{dbname}"

    user_part = quote_plus(user)
    host_part = host
    db_part = quote_plus(dbname)
    if password is None or password == "":
        return f"{normalized}://{user_part}@{host_part}:{port}/{db_part}"
    password_part = quote_plus(password)
    return f"{normalized}://{user_part}:{password_part}@{host_part}:{port}/{db_part}"


def normalize_model_provider(raw_provider: str | None) -> str:
    normalized = PROVIDER_ALIASES.get((raw_provider or "").strip().lower())
    if normalized:
        return normalized
    return "openai"


def _validate_connection(db_uri: str) -> None:
    engine = create_engine(db_uri)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def resolve_app_config(args: argparse.Namespace) -> AppConfig:
    config = _load_config_file()
    db_uri, db_uri_source = _resolve_value(
        config=config,
        config_key="DB_URI",
        cli_value=args.db_uri,
        env_key="DB_URI",
    )
    db_dialect, _ = _resolve_value(
        config=config,
        config_key="DBDIALECT",
        cli_value=args.db_dialect,
        env_key="DBDIALECT",
        default=DEFAULT_DB_DIALECT,
    )
    db_dialect = (str(db_dialect or DEFAULT_DB_DIALECT)).strip().lower()

    db_host, host_source = _resolve_value(
        config=config,
        config_key="DBHOST",
        cli_value=args.host,
        env_key="DBHOST",
    )
    db_port_raw, port_source = _resolve_value(
        config=config,
        config_key="DBPORT",
        cli_value=args.port,
        env_key="DBPORT",
        default=DEFAULT_DB_PORT,
    )
    db_name, db_name_source = _resolve_value(
        config=config,
        config_key="DBNAME",
        cli_value=args.dbname,
        env_key="DBNAME",
    )
    db_user, db_user_source = _resolve_value(
        config=config,
        config_key="DBUSER",
        cli_value=args.username,
        env_key="DBUSER",
    )
    db_password, db_password_source = _resolve_value(
        config=config,
        config_key="DBPASSWORD",
        cli_value=args.password,
        env_key="DBPASSWORD",
    )

    try:
        db_port = int(db_port_raw)
    except (TypeError, ValueError):
        db_port = _default_port_for_dialect(db_dialect)
        port_source = "default"

    if db_uri:
        while True:
            try:
                parsed_url = make_url(str(db_uri))
                db_dialect = parsed_url.get_backend_name() or db_dialect
                db_host = parsed_url.host or ""
                db_name = parsed_url.database or ""
                db_user = parsed_url.username or ""
                db_password = parsed_url.password
                db_port = int(parsed_url.port or _default_port_for_dialect(db_dialect))
                host_source = "uri" if db_host else "missing"
                db_name_source = "uri" if db_name else "missing"
                db_user_source = "uri" if db_user else "missing"
                db_password_source = "uri" if db_password is not None else "missing"
                port_source = "uri" if parsed_url.port else "default"
                _validate_connection(str(db_uri))
                break
            except (SQLAlchemyError, ValueError) as exc:
                print(f"Connection validation failed: {exc}")
                db_uri = prompt("Enter a valid SQLAlchemy DB URI: ").strip()
                db_uri_source = "prompt"
                if not db_uri:
                    db_uri = None
                    db_uri_source = "missing"
                    break

    if not db_uri:
        needs_setup = not db_host or not db_name or not db_user
        if needs_setup:
            print("Let's setup your database connection...")

        while not db_host or not db_name or not db_user:
            if not db_host:
                db_host = prompt("Enter your database host: ")
                host_source = "prompt"
            if not db_user:
                db_user = prompt("Enter your database username: ")
                db_user_source = "prompt"
            if not db_name:
                db_name = prompt("Enter the database name: ")
                db_name_source = "prompt"
            port_input = prompt(f"Enter your database port ({db_port}): ")
            if port_input:
                db_port = int(port_input)
                port_source = "prompt"

        if db_password is None:
            db_password = prompt("Enter your database password (leave empty if none): ", is_password=True)
            db_password_source = "prompt"

        while True:
            try:
                candidate_uri = _build_structured_db_uri(
                    db_dialect=db_dialect,
                    host=db_host,
                    dbname=db_name,
                    user=db_user,
                    password=db_password,
                    port=db_port,
                )
                _validate_connection(candidate_uri)
                break
            except (SQLAlchemyError, ValueError) as exc:
                print(f"Connection validation failed: {exc}")
                print("Let's setup your database connection...")
                db_dialect = (
                    prompt(f"Enter your SQL dialect [{db_dialect or DEFAULT_DB_DIALECT}]: ")
                    or db_dialect
                    or DEFAULT_DB_DIALECT
                ).strip().lower()
                db_host = prompt("Enter your database host: ")
                db_user = prompt("Enter your database username: ")
                db_name = prompt("Enter the database name: ")
                db_port_default = _default_port_for_dialect(db_dialect)
                db_port = int(prompt(f"Enter your database port ({db_port_default}): ") or db_port_default)
                db_password = prompt("Enter your database password (leave empty if none): ", is_password=True)
                host_source = "prompt"
                db_user_source = "prompt"
                db_name_source = "prompt"
                port_source = "prompt" if db_port != db_port_default else "default"
                db_password_source = "prompt"

    provider_raw = config.get("model_provider") or os.environ.get("MODEL_PROVIDER")
    if provider_raw is None:
        provider_prompt = prompt("Model provider to use (openai|anthropic|google_gemini|ollama) [openai]: ")
        provider_raw = provider_prompt or "openai"
    model_provider = normalize_model_provider(provider_raw)

    openai_api_key = config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    anthropic_api_key = config.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    google_api_key = config.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    ollama_base_url = config.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL

    if model_provider == "openai" and not openai_api_key:
        openai_api_key = prompt("Enter your OpenAI API key: ", is_password=True)
    if model_provider == "anthropic" and not anthropic_api_key:
        anthropic_api_key = prompt("Enter your Anthropic API key: ", is_password=True)
    if model_provider == "google_gemini" and not google_api_key:
        google_api_key = prompt("Enter your Google API key: ", is_password=True)
    if model_provider == "ollama" and "OLLAMA_BASE_URL" not in config and os.environ.get("OLLAMA_BASE_URL") is None:
        base_url_input = prompt(f"Ollama base URL ({DEFAULT_OLLAMA_BASE_URL}): ")
        ollama_base_url = base_url_input or DEFAULT_OLLAMA_BASE_URL

    model = config.get("model") or os.environ.get("MODEL") or os.environ.get("model")
    default_model = DEFAULT_MODELS_BY_PROVIDER.get(model_provider, DEFAULT_MODEL)
    if not model:
        user_model = prompt(f"Model to use ({default_model}): ")
        model = user_model or default_model

    sample_rows = (
        config.get("sample_rows_in_table_info")
        or os.environ.get("SAMPLE_ROWS_IN_TABLE_INFO")
        or os.environ.get("sample_rows_in_table_info")
    )
    if sample_rows is None:
        sample_rows = prompt("Number of sample rows to pass to model (Default 3): ") or 3
    sample_rows_int = int(sample_rows)

    merged = {
        "DB_URI": db_uri or "",
        "DBDIALECT": db_dialect,
        "DBHOST": db_host,
        "DBPORT": db_port,
        "DBNAME": db_name,
        "DBUSER": db_user,
        "DBPASSWORD": db_password if db_password is not None else "",
        "model_provider": model_provider,
        "OPENAI_API_KEY": openai_api_key or "",
        "ANTHROPIC_API_KEY": anthropic_api_key or "",
        "GOOGLE_API_KEY": google_api_key or "",
        "OLLAMA_BASE_URL": ollama_base_url,
        "model": model,
        "sample_rows_in_table_info": sample_rows_int,
    }
    _save_config_file(merged)

    return AppConfig(
        db_uri=db_uri,
        db_dialect=db_dialect,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        model_provider=model_provider,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        google_api_key=google_api_key,
        ollama_base_url=ollama_base_url,
        model=model,
        sample_rows_in_table_info=sample_rows_int,
        db_host_source=host_source,
        db_port_source=port_source,
        db_name_source=db_name_source,
        db_user_source=db_user_source,
        db_password_source=db_password_source,
        db_uri_source=db_uri_source if db_uri else "missing",
        db_port_mode=_port_mode(db_port, db_dialect),
        db_password_mode=_password_mode(db_password),
    )


def save_connection_config(config: AppConfig) -> None:
    existing = _load_config_file()
    existing.update(
        {
            "DB_URI": config.db_uri if config.db_uri is not None else "",
            "DBDIALECT": config.db_dialect,
            "DBHOST": config.db_host,
            "DBPORT": config.db_port,
            "DBNAME": config.db_name,
            "DBUSER": config.db_user,
            "DBPASSWORD": config.db_password if config.db_password is not None else "",
        }
    )
    _save_config_file(existing)


def get_version() -> str:
    try:
        pyproject = toml.load(os.path.join(os.path.dirname(__file__), "..", "pyproject.toml"))
        return pyproject["tool"]["poetry"]["version"]
    except Exception:
        return importlib.metadata.version("psqlomni")
