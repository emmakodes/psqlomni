import re
from typing import Any

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.tools import BaseTool, tool
from langchain_community.utilities import SQLDatabase
from langgraph.types import interrupt


_MUTATING_SQL_PREFIX = re.compile(
    r"^\s*(insert|update|delete|alter|drop|create|truncate|grant|revoke|comment|merge|upsert)",
    flags=re.IGNORECASE,
)


def _is_mutating_query(query: str) -> bool:
    return bool(_MUTATING_SQL_PREFIX.match(query or ""))


def _build_interruptible_query_tool(db: SQLDatabase) -> BaseTool:
    @tool("sql_db_query")
    def interruptible_sql_db_query(query: str) -> Any:
        """Execute a SQL query against the database after human approval."""
        decision = interrupt(
            {
                "action": "sql_db_query",
                "query": query,
                "is_mutating": _is_mutating_query(query),
            }
        )

        if isinstance(decision, str):
            return "Query execution cancelled by user."

        if not isinstance(decision, dict):
            return "Query execution cancelled: invalid interrupt response."

        action = str(decision.get("action", "")).lower().strip()
        if action in {"reject", "cancel"}:
            return "Query execution cancelled by user."

        if action in {"feedback", "response"}:
            message = str(decision.get("message", "Execution cancelled by user feedback.")).strip()
            return f"User feedback (no query executed): {message}"

        query_to_run = query
        if action == "edit":
            edited = str(decision.get("query", "")).strip()
            if not edited:
                return "Query execution cancelled: edit requested without query text."
            query_to_run = edited

        if action in {"accept", "edit"}:
            result = db.run_no_throw(query_to_run)
            if isinstance(result, str) and not result.strip():
                return "Query executed successfully. Result: no rows returned."
            return result

        return "Query execution cancelled: unknown decision."

    return interruptible_sql_db_query


def build_sql_tools(db: SQLDatabase, llm) -> dict[str, BaseTool]:
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = {tool.name: tool for tool in toolkit.get_tools()}
    tools["sql_db_query"] = _build_interruptible_query_tool(db)
    return tools
