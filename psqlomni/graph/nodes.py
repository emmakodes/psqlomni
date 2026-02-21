from typing import Annotated, Callable, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, SystemMessage
from langgraph.graph import END
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def bootstrap_list_tables(_: AgentState) -> dict[str, list[AIMessage]]:
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "sql_db_list_tables",
                        "args": {},
                        "id": "list_tables_call",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }


def make_schema_selection_node(llm, get_schema_tool) -> Callable[[AgentState], dict[str, list[AnyMessage]]]:
    llm_with_schema_tool = llm.bind_tools([get_schema_tool], tool_choice="any")

    def select_schema(state: AgentState) -> dict[str, list[AnyMessage]]:
        prompt = [
            SystemMessage(
                content=(
                    "You are a SQL assistant. Decide which tables are relevant for the user request, "
                    "then call sql_db_schema to fetch schema details before writing any SQL query."
                )
            )
        ]
        response = llm_with_schema_tool.invoke(prompt + state["messages"])
        return {"messages": [response]}

    return select_schema


def make_query_generation_node(llm, query_tool) -> Callable[[AgentState], dict[str, list[AnyMessage]]]:
    llm_with_query_tool = llm.bind_tools([query_tool])

    def generate_query_or_answer(state: AgentState) -> dict[str, list[AnyMessage]]:
        prompt = [
            SystemMessage(
                content=(
                    "You are a SQL agent for PostgreSQL. Use sql_db_query to execute SQL when needed. "
                    "Every query execution requires human approval via interrupt. "
                    "If execution is cancelled or feedback is returned, revise the SQL or explain clearly. "
                    "Never make up query results; rely on tool outputs."
                )
            )
        ]
        response = llm_with_query_tool.invoke(prompt + state["messages"])
        return {"messages": [response]}

    return generate_query_or_answer


def route_after_query_generation(state: AgentState) -> str:
    message = state["messages"][-1]
    if isinstance(message, AIMessage) and message.tool_calls:
        for tool_call in message.tool_calls:
            if tool_call.get("name") == "sql_db_query":
                return "run_query"
    return END
