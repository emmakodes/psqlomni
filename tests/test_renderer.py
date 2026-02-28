from langchain_core.messages import AIMessage, ToolMessage

from psqlomni.ui.renderer import ConsoleRenderer


def test_render_message_deduplicates_by_message_id(capsys):
    renderer = ConsoleRenderer(mode="verbose", color_enabled=False)
    seen = set()
    message = AIMessage(content="Final output", id="msg-1")

    rendered_first, content_first = renderer.render_message(message, seen)
    rendered_second, content_second = renderer.render_message(message, seen)

    assert rendered_first is True
    assert content_first == "Final output"
    assert rendered_second is False
    assert content_second is None
    output = capsys.readouterr().out
    assert output.count("[FINAL]") == 1


def test_render_message_tool_call_verbose_output(capsys):
    renderer = ConsoleRenderer(mode="verbose", color_enabled=False)
    seen = set()
    message = AIMessage(
        content="",
        id="tool-msg",
        tool_calls=[{"name": "sql_db_query", "id": "call-1", "args": {"query": "SELECT 1"}}],
    )

    rendered, content = renderer.render_message(message, seen)

    assert rendered is False
    assert content is None
    output = capsys.readouterr().out
    assert "[AGENT]" in output
    assert "[TOOL CALL]" in output
    assert "sql_db_query" in output


def test_render_message_tool_result_hidden_in_normal_mode(capsys):
    renderer = ConsoleRenderer(mode="normal", color_enabled=False)
    seen = set()
    message = ToolMessage(content="rows", name="sql_db_query", tool_call_id="c1", id="tool-1")

    rendered, content = renderer.render_message(message, seen)

    assert rendered is False
    assert content is None
    assert capsys.readouterr().out == ""
