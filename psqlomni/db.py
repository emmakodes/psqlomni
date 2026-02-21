from urllib.parse import quote_plus

from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase

from psqlomni.config import AppConfig


def build_connection_string(config: AppConfig) -> str:
    user = quote_plus(config.db_user)
    host = config.db_host
    db_name = quote_plus(config.db_name)
    if config.db_password is None or config.db_password == "":
        return f"postgresql://{user}@{host}:{config.db_port}/{db_name}"

    password = quote_plus(config.db_password)
    return f"postgresql://{user}:{password}@{host}:{config.db_port}/{db_name}"


def build_engine(config: AppConfig):
    return create_engine(build_connection_string(config))


def build_sql_database(config: AppConfig) -> SQLDatabase:
    return SQLDatabase.from_uri(
        build_connection_string(config),
        sample_rows_in_table_info=config.sample_rows_in_table_info,
    )
