from urllib.parse import quote_plus

from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase

from psqlomni.config import AppConfig


def build_connection_string(config: AppConfig) -> str:
    if config.db_uri:
        return config.db_uri

    dialect = (config.db_dialect or "postgresql").strip().lower()
    if dialect.startswith("sqlite"):
        if config.db_name in {"", ":memory:"}:
            return "sqlite:///:memory:"
        if config.db_name.startswith("/"):
            return f"sqlite:////{config.db_name.lstrip('/')}"
        return f"sqlite:///{config.db_name}"

    user = quote_plus(config.db_user)
    host = config.db_host
    db_name = quote_plus(config.db_name)
    if config.db_password is None or config.db_password == "":
        return f"{dialect}://{user}@{host}:{config.db_port}/{db_name}"

    password = quote_plus(config.db_password)
    return f"{dialect}://{user}:{password}@{host}:{config.db_port}/{db_name}"


def build_engine(config: AppConfig):
    return create_engine(build_connection_string(config))


def build_sql_database(config: AppConfig) -> SQLDatabase:
    return SQLDatabase.from_uri(
        build_connection_string(config),
        sample_rows_in_table_info=config.sample_rows_in_table_info,
    )
