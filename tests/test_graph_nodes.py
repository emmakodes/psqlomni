from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END

from psqlomni.graph.nodes import (
    bootstrap_list_tables,
    make_schema_selection_node,
    route_after_query_generation,
)


class FakeBoundLLM:
    def __init__(self, response):
        self.response = response

    def invoke(self, _messages):
        return self.response


class FakeLLM:
    def __init__(self, response):
        self.response = response

    def bind_tools(self, _tools):
        return FakeBoundLLM(self.response)


def test_bootstrap_list_tables_creates_expected_tool_call():
    result = bootstrap_list_tables({"messages": []})
    message = result["messages"][0]
    assert isinstance(message, AIMessage)
    assert message.tool_calls[0]["name"] == "sql_db_list_tables"
    assert message.tool_calls[0]["id"] == "list_tables_call"


def test_make_schema_selection_node_falls_back_when_no_tool_call():
    llm = FakeLLM(AIMessage(content="No tool chosen"))
    node = make_schema_selection_node(llm, get_schema_tool=object())
    state = {
        "messages": [
            ToolMessage(content="users,orders", name="sql_db_list_tables", tool_call_id="list_tables_call")
        ]
    }
    result = node(state)
    message = result["messages"][0]
    assert isinstance(message, AIMessage)
    assert message.tool_calls[0]["name"] == "sql_db_schema"
    assert message.tool_calls[0]["args"]["table_names"] == "users,orders"


def test_make_schema_selection_node_uses_llm_tool_call_when_present():
    response = AIMessage(
        content="",
        tool_calls=[{"name": "sql_db_schema", "args": {"table_names": "users"}, "id": "x", "type": "tool_call"}],
    )
    llm = FakeLLM(response)
    node = make_schema_selection_node(llm, get_schema_tool=object())
    result = node({"messages": []})
    assert result["messages"][0] == response


def test_route_after_query_generation():
    run_query_state = {
        "messages": [AIMessage(content="", tool_calls=[{"name": "sql_db_query", "args": {}, "id": "1"}])]
    }
    done_state = {"messages": [AIMessage(content="Final answer", tool_calls=[])]}
    assert route_after_query_generation(run_query_state) == "run_query"
    assert route_after_query_generation(done_state) == END
