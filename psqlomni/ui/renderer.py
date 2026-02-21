import json
import os
import sys
import textwrap
from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


@dataclass
class ConsoleRenderer:
    mode: str = "verbose"
    max_content_width: int = 1000
    color_enabled: bool = True
    process_faint: bool = True

    def __post_init__(self) -> None:
        if not self.color_enabled:
            return
        if os.environ.get("NO_COLOR"):
            self.color_enabled = False
            return
        if not sys.stdout.isatty():
            self.color_enabled = False

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def is_verbose(self) -> bool:
        return self.mode == "verbose"

    def print_user(self, text: str) -> None:
        print(f"\n{self._colorize('[USER]', 'cyan', bold=True)}")
        print(text)

    def print_final(self, text: str) -> None:
        print(f"\n{self._colorize('[FINAL]', 'green', bold=True)}")
        print(text)

    def print_agent(self, text: str) -> None:
        print(f"\n{self._process_label('[AGENT]', 'magenta')}")
        print(self._process_text(text))

    def print_tool_call(self, name: str, call_id: str, args: dict) -> None:
        print(f"\n{self._process_label('[TOOL CALL]', 'yellow')}")
        print(self._process_text(f"name: {name}"))
        if call_id:
            print(self._process_text(f"call_id: {call_id}"))
        if args:
            print(self._process_text("args:"))
            print(self._process_text(self._safe_json(args)))

    def print_tool_result(self, name: str, content: str) -> None:
        label = f"[TOOL RESULT:{name}]"
        print(f"\n{self._process_label(label, 'blue')}")
        print(self._process_text(self._truncate(content)))

    def print_approval_prompt(self, query: str, is_mutating: bool) -> None:
        print(f"\n{self._colorize('[APPROVAL REQUIRED]', 'red', bold=True)}")
        print(self._process_text("action: sql_db_query"))
        print(self._process_text("sql:"))
        print(self._process_text(query))
        print(self._process_text("choices: [a]ccept  [e]dit query  [f]eedback  [c]ancel"))

    def print_turn_summary(self, tool_calls: int, tool_results: int, approvals: int) -> None:
        if not self.is_verbose():
            return
        print(f"\n{self._process_label('[TURN SUMMARY]', 'white')}")
        print(self._process_text(f"tool_calls={tool_calls} tool_results={tool_results} approvals={approvals}"))

    def render_message(self, message, seen_messages: set[str]) -> tuple[bool, str | None]:
        message_id = getattr(message, "id", None)
        if message_id is None:
            message_id = (
                f"{type(message).__name__}|{getattr(message, 'name', '')}|"
                f"{getattr(message, 'tool_call_id', '')}|{getattr(message, 'content', '')}|"
                f"{getattr(message, 'tool_calls', '')}"
            )

        if message_id in seen_messages:
            return False, None
        seen_messages.add(message_id)

        if isinstance(message, HumanMessage):
            return False, None

        if isinstance(message, AIMessage):
            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                if self.is_verbose():
                    self.print_agent("Preparing tool calls.")
                    for tool_call in tool_calls:
                        self.print_tool_call(
                            name=tool_call.get("name", "unknown"),
                            call_id=tool_call.get("id", ""),
                            args=tool_call.get("args", {}),
                        )
                return False, None

            content = self._coerce_content(message.content)
            if content.strip():
                self.print_final(content)
                return True, content
            return False, None

        if isinstance(message, ToolMessage):
            if self.is_verbose():
                self.print_tool_result(
                    getattr(message, "name", "tool"),
                    self._coerce_content(message.content),
                )
            return False, None

        return False, None

    def _safe_json(self, payload: dict) -> str:
        try:
            return json.dumps(payload, indent=2, ensure_ascii=True)
        except TypeError:
            return str(payload)

    def _coerce_content(self, content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(str(item) for item in content)
        return str(content)

    def _truncate(self, content: str) -> str:
        normalized = content.strip()
        if not normalized:
            return "(empty)"
        if len(normalized) <= self.max_content_width:
            return normalized
        clipped = textwrap.shorten(normalized, width=self.max_content_width, placeholder=" ...[truncated]")
        return clipped

    def _process_label(self, text: str, color: str) -> str:
        return self._colorize(text, color, bold=not self.process_faint, dim=self.process_faint)

    def _process_text(self, text: str) -> str:
        if not self.process_faint:
            return text
        return self._colorize(text, "white", dim=True)

    def _colorize(self, text: str, color: str, bold: bool = False, dim: bool = False) -> str:
        if not self.color_enabled:
            return text
        colors = {
            "red": "\033[31m",
            "green": "\033[32m",
            "yellow": "\033[33m",
            "blue": "\033[34m",
            "magenta": "\033[35m",
            "cyan": "\033[36m",
            "white": "\033[37m",
            "dim": "\033[2m",
        }
        prefix = ""
        if bold:
            prefix += "\033[1m"
        if dim:
            prefix += "\033[2m"
        prefix += colors.get(color, "")
        suffix = "\033[0m"
        return f"{prefix}{text}{suffix}" if prefix else text
