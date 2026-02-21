import argparse
import importlib.metadata
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2
import toml
from prompt_toolkit import prompt

DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_DB_PORT = 5432
CONFIG_FILE = Path(os.path.expanduser("~/.psqlomni"))
_MISSING = object()


@dataclass
class AppConfig:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str | None
    openai_api_key: str
    model: str
    sample_rows_in_table_info: int
    db_host_source: str
    db_port_source: str
    db_name_source: str
    db_user_source: str
    db_password_source: str
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


def _port_mode(port: int) -> str:
    if int(port) == DEFAULT_DB_PORT:
        return f"default({DEFAULT_DB_PORT})"
    return f"custom({port})"


def _validate_connection(host: str, dbname: str, user: str, password: str | None, port: int) -> None:
    kwargs = {
        "host": host,
        "dbname": dbname,
        "user": user,
        "port": port,
        "connect_timeout": 10,
    }
    if password is not None and password != "":
        kwargs["password"] = password

    conn = psycopg2.connect(**kwargs)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT version();")
    finally:
        conn.close()


def resolve_app_config(args: argparse.Namespace) -> AppConfig:
    config = _load_config_file()

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
        db_port = DEFAULT_DB_PORT
        port_source = "default"

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

    try:
        _validate_connection(db_host, db_name, db_user, db_password, db_port)
    except psycopg2.OperationalError as exc:
        print(f"Connection validation failed: {exc}")
        print("Let's setup your database connection...")
        while True:
            db_host = prompt("Enter your database host: ")
            db_user = prompt("Enter your database username: ")
            db_name = prompt("Enter the database name: ")
            db_port = int(prompt(f"Enter your database port ({DEFAULT_DB_PORT}): ") or DEFAULT_DB_PORT)
            db_password = prompt("Enter your database password (leave empty if none): ", is_password=True)
            host_source = "prompt"
            db_user_source = "prompt"
            db_name_source = "prompt"
            port_source = "prompt" if db_port != DEFAULT_DB_PORT else "default"
            db_password_source = "prompt"
            try:
                _validate_connection(db_host, db_name, db_user, db_password, db_port)
                break
            except psycopg2.OperationalError as prompt_exc:
                print(f"Error: {prompt_exc}")

    api_key = config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if api_key is None:
        api_key = prompt("Enter your OpenAI API key: ", is_password=True)

    model = config.get("model") or os.environ.get("model") or DEFAULT_MODEL
    if "model" not in config and os.environ.get("model") is None:
        user_model = prompt(f"Model to use ({DEFAULT_MODEL}): ")
        model = user_model or DEFAULT_MODEL

    sample_rows = config.get("sample_rows_in_table_info") or os.environ.get("sample_rows_in_table_info")
    if sample_rows is None:
        sample_rows = prompt("Number of sample rows to pass to model (Default 3): ") or 3
    sample_rows_int = int(sample_rows)

    merged = {
        "DBHOST": db_host,
        "DBPORT": db_port,
        "DBNAME": db_name,
        "DBUSER": db_user,
        "DBPASSWORD": db_password if db_password is not None else "",
        "OPENAI_API_KEY": api_key,
        "model": model,
        "sample_rows_in_table_info": sample_rows_int,
    }
    _save_config_file(merged)

    return AppConfig(
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        openai_api_key=api_key,
        model=model,
        sample_rows_in_table_info=sample_rows_int,
        db_host_source=host_source,
        db_port_source=port_source,
        db_name_source=db_name_source,
        db_user_source=db_user_source,
        db_password_source=db_password_source,
        db_port_mode=_port_mode(db_port),
        db_password_mode=_password_mode(db_password),
    )


def save_connection_config(config: AppConfig) -> None:
    existing = _load_config_file()
    existing.update(
        {
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
