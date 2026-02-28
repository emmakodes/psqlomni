from psqlomni.tools import sql_tools


class FakeDB:
    def __init__(self, result="ok"):
        self.result = result
        self.queries = []

    def run_no_throw(self, query: str):
        self.queries.append(query)
        return self.result


def _invoke_tool(db: FakeDB, decision, query="SELECT 1"):
    tool = sql_tools._build_interruptible_query_tool(db)
    original_interrupt = sql_tools.interrupt
    try:
        sql_tools.interrupt = lambda _: decision
        return tool.invoke({"query": query})
    finally:
        sql_tools.interrupt = original_interrupt


def test_is_mutating_query():
    assert sql_tools._is_mutating_query("UPDATE users SET name='x'") is True
    assert sql_tools._is_mutating_query("  delete from users") is True
    assert sql_tools._is_mutating_query("SELECT * FROM users") is False


def test_interrupt_string_decision_cancels():
    db = FakeDB()
    result = _invoke_tool(db, "cancel")
    assert result == "Query execution cancelled by user."
    assert db.queries == []


def test_interrupt_invalid_decision_type_cancels():
    db = FakeDB()
    result = _invoke_tool(db, 123)
    assert result == "Query execution cancelled: invalid interrupt response."
    assert db.queries == []


def test_reject_and_feedback_branches():
    reject_db = FakeDB()
    reject_result = _invoke_tool(reject_db, {"action": "reject"})
    assert reject_result == "Query execution cancelled by user."
    assert reject_db.queries == []

    feedback_db = FakeDB()
    feedback_result = _invoke_tool(feedback_db, {"action": "feedback", "message": "Need a date filter."})
    assert feedback_result == "User feedback (no query executed): Need a date filter."
    assert feedback_db.queries == []


def test_edit_accept_and_unknown_actions():
    edit_db = FakeDB(result="rows")
    edit_result = _invoke_tool(edit_db, {"action": "edit", "query": "SELECT 2"}, query="SELECT 1")
    assert edit_result == "rows"
    assert edit_db.queries == ["SELECT 2"]

    blank_edit_db = FakeDB()
    blank_edit_result = _invoke_tool(blank_edit_db, {"action": "edit", "query": "  "})
    assert blank_edit_result == "Query execution cancelled: edit requested without query text."
    assert blank_edit_db.queries == []

    accept_db = FakeDB(result="   ")
    accept_result = _invoke_tool(accept_db, {"action": "accept"}, query="SELECT 1")
    assert accept_result == "Query executed successfully. Result: no rows returned."
    assert accept_db.queries == ["SELECT 1"]

    unknown_db = FakeDB()
    unknown_result = _invoke_tool(unknown_db, {"action": "maybe"})
    assert unknown_result == "Query execution cancelled: unknown decision."
    assert unknown_db.queries == []
