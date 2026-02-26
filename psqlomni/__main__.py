from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command
import psycopg2
from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import ConditionalCompleter, WordCompleter
from prompt_toolkit.filters import Condition
from prompt_toolkit import PromptSession
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog

from psqlomni.config import (
    DEFAULT_MODELS_BY_PROVIDER,
    DEFAULT_OLLAMA_BASE_URL,
    MODEL_CATALOG_BY_PROVIDER,
    PROVIDER_ALIASES,
    get_version,
    parse_args,
    resolve_app_config,
    save_connection_config,
)
from psqlomni.db import build_sql_database
from psqlomni.graph.builder import build_sql_graph
from psqlomni.llm import build_llm
from psqlomni.tools.sql_tools import build_sql_tools
from psqlomni.ui.renderer import ConsoleRenderer


class PSqlomni:
    def __init__(self) -> None:
        args = parse_args()
        self.config = resolve_app_config(args)
        self.db = build_sql_database(self.config)
        self.llm = build_llm(self.config)
        self.tools = build_sql_tools(self.db, self.llm)
        self.graph = build_sql_graph(self.llm, self.tools)
        self.thread_id = str(uuid4())
        self.known_thread_ids = {self.thread_id}
        self.renderer = ConsoleRenderer(mode="verbose")
        self.slash_commands = [
            "/help",
            "/connection",
            "/disconnect",
            "/connect",
            "/mode",
            "/provider",
            "/model",
            "/new",
            "/resume",
            "/exit",
        ]
        self.slash_completer = WordCompleter(self.slash_commands, ignore_case=True)
        self.command_menu_items = [
            ("/help", "show commands"),
            ("/connection", "show current db connection + provider + model + mode + thread"),
            ("/disconnect", "disconnect current database session"),
            ("/connect", "connect to a different database"),
            ("/mode normal", "set compact output"),
            ("/mode verbose", "set full process output"),
            ("/provider", "show provider"),
            ("/provider <name>", "set provider: openai|anthropic|google_gemini|ollama"),
            ("/model", "show current model"),
            ("/model list", "show built-in model list for provider"),
            ("/new", "start a new chat thread"),
            ("/resume", "resume a prior in-memory thread"),
            ("/exit", "quit"),
        ]

    def chat_loop(self) -> None:
        slash_only_completer = ConditionalCompleter(
            self.slash_completer,
            filter=Condition(lambda: get_app().current_buffer.document.text.lstrip().startswith("/")),
        )
        session = PromptSession(completer=slash_only_completer, complete_while_typing=True)

        print(
            """
Welcome to PSQLOMNI (LangGraph SQL Agent).
Commands:
  /                   Show slash commands
  /help               Show slash commands
  /connection         Show current DB connection + provider + model
  /disconnect         Disconnect current database session
  /connect            Connect to a different database
  /mode <value>       Output level: normal|verbose
  /provider [name]    Show or set provider
  /model              Show model + open model picker
  /model list         Show known models for provider
  /model [name]       Set model for this session
  /new                Start a new chat thread
  /resume <thread_id> Resume a previous in-memory thread
  /exit               Quit
            """.strip()
        )
        print(
            "Using connection "
            f"{self.config.db_host}:{self.config.db_port}/{self.config.db_name} as {self.config.db_user} "
            f"(port={self.config.db_port_mode}, password={self.config.db_password_mode})"
        )

        while True:
            try:
                cmd = session.prompt("\n> ").strip()
                if not cmd:
                    continue
                if cmd == "/":
                    picked = self._pick_slash_command()
                    if not picked:
                        continue
                    cmd = picked
                if self._handle_slash_or_legacy_command(cmd):
                    continue
                if cmd in {"/exit", "exit"}:
                    return

                self.process_command(cmd)
            except (KeyboardInterrupt, EOFError):
                return

    def _show_slash_help(self) -> None:
        print(
            """
/
  /help               show commands
  /connection         show current db connection + provider + model + mode + thread
  /disconnect         disconnect current database session
  /connect            connect to a different database
  /mode <value>       set output mode: normal|verbose
  /provider [name]    show provider, or set provider
  /model              show model + open model picker for this provider
  /model list         show known models for this provider
  /model <name>       set model for this session
  /new                start a new chat thread
  /resume <thread_id> resume a prior in-memory thread
  /exit               quit
            """.strip()
        )

    def _pick_slash_command(self) -> str | None:
        values = [(value, f"{value:<14} {desc}") for value, desc in self.command_menu_items]
        selection = radiolist_dialog(
            title="PSQLOMNI Commands",
            text="Use arrow keys, then Enter to select a command.",
            values=values,
            ok_text="Select",
            cancel_text="Cancel",
        ).run()
        if not selection:
            return None
        return selection

    def _handle_slash_or_legacy_command(self, cmd: str) -> bool:
        if cmd in {"/", "/help", "help"}:
            self._show_slash_help()
            return True

        if cmd in {"/connection", "connection"}:
            connected = self.graph is not None
            if connected:
                print(
                    f"Host: {self.config.db_host}, Database: {self.config.db_name}, User: {self.config.db_user}"
                )
                print(
                    f"Port: {self.config.db_port_mode} [{self.config.db_port_source}]"
                )
                print(
                    f"Password: {self.config.db_password_mode} [{self.config.db_password_source}]"
                )
            else:
                print("Database: DISCONNECTED")
            print(f"Provider: {self.config.model_provider}")
            print(f"Model: {self.config.model}")
            print(f"Version: {get_version()}")
            print(f"Output mode: {self.renderer.mode}")
            print(f"Thread: {self.thread_id}")
            return True

        if cmd in {"/disconnect", "disconnect"}:
            self._disconnect_database()
            return True

        if cmd in {"/connect", "connect"}:
            self._connect_database_interactive()
            return True

        if cmd.startswith("/mode ") or cmd.startswith("mode "):
            mode = cmd.split(" ", 1)[1].strip().lower()
            if mode not in {"normal", "verbose"}:
                print("Invalid mode. Use: /mode normal|verbose")
                return True
            self.renderer.set_mode(mode)
            print(f"Output mode set to: {mode}")
            return True

        if cmd in {"/provider", "provider"}:
            print(f"Current provider: {self.config.model_provider}")
            print("Usage: /provider <openai|anthropic|google_gemini|ollama>")
            return True

        if cmd.startswith("/provider "):
            raw_provider = cmd.split(" ", 1)[1].strip().lower()
            if not raw_provider:
                print("Provider cannot be empty. Usage: /provider <name>")
                return True
            if raw_provider not in PROVIDER_ALIASES:
                print("Unsupported provider. Use: openai|anthropic|google_gemini|ollama")
                return True

            provider = PROVIDER_ALIASES[raw_provider]
            previous_provider = self.config.model_provider
            previous_model = self.config.model
            previous_runtime = (self.llm, self.tools, self.graph)
            self.config.model_provider = provider
            self.config.model = DEFAULT_MODELS_BY_PROVIDER.get(provider, self.config.model)

            if provider == "openai" and not self.config.openai_api_key:
                self.config.openai_api_key = prompt("Enter your OpenAI API key: ", is_password=True)
            if provider == "anthropic" and not self.config.anthropic_api_key:
                self.config.anthropic_api_key = prompt("Enter your Anthropic API key: ", is_password=True)
            if provider == "google_gemini" and not self.config.google_api_key:
                self.config.google_api_key = prompt("Enter your Google API key: ", is_password=True)
            if provider == "ollama" and not self.config.ollama_base_url:
                self.config.ollama_base_url = (
                    prompt(f"Ollama base URL ({DEFAULT_OLLAMA_BASE_URL}): ") or DEFAULT_OLLAMA_BASE_URL
                )

            try:
                self._rebuild_model_runtime()
            except Exception as exc:
                self.config.model_provider = previous_provider
                self.config.model = previous_model
                self.llm, self.tools, self.graph = previous_runtime
                print(f"Unable to switch provider: {exc}")
                return True

            picked_model = self._pick_model_interactive()
            if picked_model:
                self.config.model = picked_model
                try:
                    self._rebuild_model_runtime()
                except Exception as exc:
                    print(f"Provider switched, but model '{picked_model}' failed to load: {exc}")
                    self.config.model = DEFAULT_MODELS_BY_PROVIDER.get(provider, self.config.model)
                    try:
                        self._rebuild_model_runtime()
                    except Exception as default_exc:
                        self.config.model_provider = previous_provider
                        self.config.model = previous_model
                        self.llm, self.tools, self.graph = previous_runtime
                        print(f"Reverted provider/model due to error: {default_exc}")
            print(f"Provider set for this session: {provider}")
            print(f"Model set for this session: {self.config.model}")
            return True

        if cmd in {"/model", "model"}:
            print(f"Current provider: {self.config.model_provider}")
            print(f"Current model: {self.config.model}")
            print("Usage: /model | /model list | /model <model_name>")
            picked_model = self._pick_model_interactive()
            if picked_model:
                previous_model = self.config.model
                previous_runtime = (self.llm, self.tools, self.graph)
                self.config.model = picked_model
                try:
                    self._rebuild_model_runtime()
                    print(f"Model set for this session: {self.config.model}")
                except Exception as exc:
                    self.config.model = previous_model
                    self.llm, self.tools, self.graph = previous_runtime
                    print(f"Unable to set model: {exc}")
            return True

        if cmd in {"/model list", "model list"}:
            self._print_model_catalog(self.config.model_provider)
            return True

        if cmd.startswith("/model "):
            model = cmd.split(" ", 1)[1].strip()
            if not model:
                print("Model cannot be empty. Usage: /model <model_name>")
                return True
            previous_model = self.config.model
            previous_runtime = (self.llm, self.tools, self.graph)
            self.config.model = model
            try:
                self._rebuild_model_runtime()
            except Exception as exc:
                self.config.model = previous_model
                self.llm, self.tools, self.graph = previous_runtime
                print(f"Unable to set model: {exc}")
                return True
            print(f"Model set for this session: {model}")
            return True

        if cmd in {"/new", "new"}:
            self.thread_id = str(uuid4())
            self.known_thread_ids.add(self.thread_id)
            print(f"Started new thread: {self.thread_id}")
            return True

        if cmd.startswith("/resume "):
            thread_id = cmd.split(" ", 1)[1].strip()
            if not thread_id:
                print("Usage: /resume <thread_id>")
                return True
            if thread_id not in self.known_thread_ids:
                print("Unknown thread id for this session.")
                print("Use /connection to see current thread or /new to start one.")
                return True
            self.thread_id = thread_id
            print(f"Resumed thread: {thread_id}")
            return True

        if cmd in {"/exit", "exit"}:
            return False

        return False

    def _disconnect_database(self) -> None:
        self.db = None
        self.tools = None
        self.graph = None
        self.thread_id = str(uuid4())
        self.known_thread_ids.add(self.thread_id)
        print("Disconnected from database.")
        print("Use /connect to connect to another database.")

    def _rebuild_model_runtime(self) -> None:
        self.llm = build_llm(self.config)
        if self.db is None:
            self.tools = None
            self.graph = None
            return
        self.tools = build_sql_tools(self.db, self.llm)
        self.graph = build_sql_graph(self.llm, self.tools)

    def _print_model_catalog(self, provider: str) -> None:
        models = MODEL_CATALOG_BY_PROVIDER.get(provider, [])
        if not models:
            print(f"No built-in models listed for provider: {provider}")
            return
        print(f"Known models for {provider}:")
        for model in models:
            marker = "*" if model == self.config.model else "-"
            print(f"  {marker} {model}")

    def _pick_model_interactive(self) -> str | None:
        provider = self.config.model_provider
        models = MODEL_CATALOG_BY_PROVIDER.get(provider, [])
        if not models:
            return None

        current = self.config.model if self.config.model in models else models[0]
        values = []
        for model in models:
            label = f"{model}"
            if model == self.config.model:
                label = f"{model} (current)"
            values.append((model, label))
        values.append(("__custom__", "Custom model name..."))

        selected = radiolist_dialog(
            title=f"Models ({provider})",
            text="Select a model for this provider.",
            values=values,
            default=current,
            ok_text="Select",
            cancel_text="Cancel",
        ).run()
        if not selected:
            return None
        if selected == "__custom__":
            custom = prompt("Enter model name: ").strip()
            if not custom:
                print("Model unchanged.")
                return None
            return custom
        return selected

    def _connect_database_interactive(self) -> None:
        current_port = self.config.db_port or 5432

        host = (prompt(f"DB host [{self.config.db_host}]: ") or self.config.db_host).strip()
        dbname = (prompt(f"DB name [{self.config.db_name}]: ") or self.config.db_name).strip()
        user = (prompt(f"DB user [{self.config.db_user}]: ") or self.config.db_user).strip()
        port_raw = (prompt(f"DB port [{current_port}]: ") or str(current_port)).strip()
        password_input = prompt("DB password (leave blank to reuse current): ", is_password=True)
        password = password_input
        password_source = "prompt"
        if not password:
            password = self.config.db_password
            password_source = self.config.db_password_source

        try:
            port = int(port_raw)
        except ValueError:
            print("Invalid port. Connection aborted.")
            return

        if not host or not dbname or not user:
            print("Host, database, and user are required. Connection aborted.")
            return

        try:
            kwargs = {
                "host": host,
                "dbname": dbname,
                "user": user,
                "port": port,
                "connect_timeout": 10,
            }
            if password is not None and password != "":
                kwargs["password"] = password
            conn = psycopg2.connect(**kwargs)
            conn.close()
        except psycopg2.OperationalError as exc:
            print(f"Connection failed: {exc}")
            return

        self.config.db_host = host
        self.config.db_name = dbname
        self.config.db_user = user
        self.config.db_port = port
        self.config.db_password = password
        self.config.db_host_source = "prompt"
        self.config.db_name_source = "prompt"
        self.config.db_user_source = "prompt"
        self.config.db_port_source = "prompt" if port != 5432 else "default"
        self.config.db_password_source = password_source
        self.config.db_port_mode = f"default(5432)" if port == 5432 else f"custom({port})"
        if password is None:
            self.config.db_password_mode = "missing"
        elif password == "":
            self.config.db_password_mode = "blank"
        else:
            self.config.db_password_mode = "set"

        self.db = build_sql_database(self.config)
        self.tools = build_sql_tools(self.db, self.llm)
        self.graph = build_sql_graph(self.llm, self.tools)
        save_connection_config(self.config)
        self.thread_id = str(uuid4())
        self.known_thread_ids.add(self.thread_id)
        print(f"Connected to {host}:{port}/{dbname} as {user}")
        print(f"Started new thread: {self.thread_id}")

    def process_command(self, cmd: str) -> None:
        if self.graph is None:
            print("No active database connection. Use /connect first.")
            return

        runtime_config = {"configurable": {"thread_id": self.thread_id}}
        stream_input = {"messages": [("user", cmd)]}
        seen_messages: set[str] = set()
        self.renderer.print_user(cmd)

        tool_call_count = 0
        tool_result_count = 0
        approval_count = 0

        while True:
            interrupted = False
            payload = None

            for step in self.graph.stream(stream_input, config=runtime_config, stream_mode="values"):
                if "__interrupt__" in step:
                    interrupted = True
                    interrupt_obj = step["__interrupt__"][0]
                    payload = getattr(interrupt_obj, "value", interrupt_obj)
                    break

                messages = step.get("messages", [])
                if messages:
                    message = messages[-1]
                    if isinstance(message, AIMessage) and message.tool_calls:
                        tool_call_count += len(message.tool_calls)
                    if isinstance(message, ToolMessage):
                        tool_result_count += 1
                    self.renderer.render_message(message, seen_messages)

            if not interrupted:
                self.renderer.print_turn_summary(
                    tool_calls=tool_call_count,
                    tool_results=tool_result_count,
                    approvals=approval_count,
                )
                return

            approval_count += 1
            decision = self._prompt_query_decision(payload)
            stream_input = Command(resume=decision)

    def _prompt_query_decision(self, payload):
        query = payload.get("query", "") if isinstance(payload, dict) else ""
        is_mutating = bool(payload.get("is_mutating")) if isinstance(payload, dict) else False

        self.renderer.print_approval_prompt(query=query, is_mutating=is_mutating)

        while True:
            choice = (prompt("Decision (a/e/f/c): ") or "").strip().lower()

            if choice in {"a", "accept"}:
                return {"action": "accept"}

            if choice in {"e", "edit"}:
                edited = prompt("Edited SQL: ").strip()
                if edited:
                    return {"action": "edit", "query": edited}
                print("Edited SQL cannot be empty.")
                continue

            if choice in {"f", "feedback"}:
                message = prompt("Feedback to assistant (no execution): ").strip()
                if message:
                    return {"action": "feedback", "message": message}
                print("Feedback cannot be empty.")
                continue

            if choice in {"c", "cancel", "reject"}:
                return {"action": "cancel"}

            print("Invalid choice. Use a/e/f/c.")


def main():
    psqlomni = PSqlomni()
    psqlomni.chat_loop()


if __name__ == "__main__":
    main()
