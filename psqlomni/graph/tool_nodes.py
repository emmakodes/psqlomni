from dataclasses import dataclass

from langgraph.prebuilt import ToolNode


@dataclass
class SQLToolNodes:
    list_tables_node: ToolNode
    get_schema_node: ToolNode
    run_query_node: ToolNode


def build_tool_nodes(tools: dict):
    return SQLToolNodes(
        list_tables_node=ToolNode([tools["sql_db_list_tables"]]),
        get_schema_node=ToolNode([tools["sql_db_schema"]]),
        run_query_node=ToolNode([tools["sql_db_query"]]),
    )
