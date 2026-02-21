from langgraph.graph import START, StateGraph

from psqlomni.graph.nodes import (
    AgentState,
    bootstrap_list_tables,
    make_query_generation_node,
    make_schema_selection_node,
    route_after_query_generation,
)
from psqlomni.graph.tool_nodes import build_tool_nodes

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # pragma: no cover
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver


def build_sql_graph(llm, tools):
    tool_nodes = build_tool_nodes(tools)

    graph = StateGraph(AgentState)
    graph.add_node("bootstrap_list_tables", bootstrap_list_tables)
    graph.add_node("list_tables", tool_nodes.list_tables_node)
    graph.add_node("select_schema", make_schema_selection_node(llm, tools["sql_db_schema"]))
    graph.add_node("get_schema", tool_nodes.get_schema_node)
    graph.add_node("generate_query", make_query_generation_node(llm, tools["sql_db_query"]))
    graph.add_node("run_query", tool_nodes.run_query_node)

    graph.add_edge(START, "bootstrap_list_tables")
    graph.add_edge("bootstrap_list_tables", "list_tables")
    graph.add_edge("list_tables", "select_schema")
    graph.add_edge("select_schema", "get_schema")
    graph.add_edge("get_schema", "generate_query")
    graph.add_conditional_edges("generate_query", route_after_query_generation)
    graph.add_edge("run_query", "generate_query")

    return graph.compile(checkpointer=InMemorySaver())
