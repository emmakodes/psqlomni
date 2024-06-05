import argparse
from datetime import datetime
import importlib.metadata
import json
import os
import psycopg2
import toml
from prompt_toolkit import PromptSession, prompt
from halo import Halo
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain.agents.agent import AgentExecutor
from langchain_community.agent_toolkits.sql.prompt import SQL_FUNCTIONS_SUFFIX
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain.agents import tool
from langchain.agents.format_scratchpad.openai_tools import format_to_openai_tool_messages
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field

from typing import Any, Dict, Optional, Sequence, Type, Union
from sqlalchemy.engine import Result
from langchain_core.callbacks import (
    CallbackManagerForToolRun,
)
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.tools import BaseTool
from langchain.memory import ConversationBufferWindowMemory

GPT_MODEL3="gpt-3.5-turbo-0125" # "gpt-3.5-turbo-1106"
GPT_MODEL4="gpt-4-1106-preview"

MEMORY_KEY = "chat_history"
memory = ConversationBufferWindowMemory(k=3, memory_key=MEMORY_KEY, return_messages=True)

spinner = Halo(text='thinking', spinner='dots')


class BaseSQLDatabaseTool(BaseModel):
    """Base tool for interacting with a SQL database."""
    
    db: SQLDatabase = Field(exclude=True)

    class Config(BaseTool.Config):
        pass


class _QuerySQLDataBaseToolInput(BaseModel):
    query: str = Field(..., description="A detailed and correct SQL query.")


class QuerySQLDataBaseTool(BaseSQLDatabaseTool, BaseTool):
    """Tool for querying a SQL database."""

    name: str = "sql_db_query"
    description: str = """
    Execute a SQL query against the database and get back the result..
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    """
    args_schema: Type[BaseModel] = _QuerySQLDataBaseToolInput

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Union[str, Sequence[Dict[str, Any]], Result]:
        """Execute the query, return the results or an error message."""
        spinner.stop()
        _continue = input(f"Should the agent execute the following query:\n{query}\n(Y/n)?: ") or "Y"
        spinner.start("thinking...")
        if _continue.lower() == "y":
            return self.db.run_no_throw(query)
        
        return "Response: Query not Executed as it should not be executed. Don't try executing the query again as it is not allowed by the user. Execution stopped by the user as the user does not want to proceed with executing the query."


class PSqlomni:
    CONFIG_FILE = os.path.expanduser('~/.psqlomni')

    def __init__(self) -> None:
        self.load_config()
        self.llm:ChatOpenAI
        self.db: SQLDatabase = None

        args = self.parse_args()

        if 'DBUSER' in self.config and 'DBHOST' in self.config:
            db_username = self.config['DBUSER']
            db_password = self.config['DBPASSWORD']
            db_host = self.config['DBHOST']
            db_port = int(self.config['DBPORT'])
            db_name = self.config['DBNAME']
        else:
            db_username = args.username or os.environ.get('DBUSER')
            db_password = args.password or os.environ.get('DBPASSWORD')
            db_host = args.host or os.environ.get('DBHOST')
            db_port = args.port or 5432
            db_name = args.dbname or os.environ.get('DBNAME')

        if db_host is None:
            connection_good = False
            while not connection_good:
                print("Let's setup your database connection...")
                db_host = prompt("Enter your database host: ")
                db_username = prompt("Enter your database username: ")
                db_password = prompt("Enter your database password: ", is_password=True)
                db_name = prompt("Enter the database name: ")
                db_port = prompt("Enter your database port (5432): ") or 5432
                db_port = int(db_port)
                print("Validating connection info...")
                try:
                    pgconn = psycopg2.connect(
                        f"host={db_host} dbname={db_name} user={db_username} password={db_password}",
                        connect_timeout=10
                    )
                    with pgconn.cursor() as cursor:
                        cursor.execute("SELECT version();")
                    connection_good = True
                    print("Validation done.")
                except psycopg2.OperationalError as e:
                    print("Error: ", e)
                    continue

                self.config |= {
                    "DBUSER": db_username,
                    "DBPASSWORD": db_password,
                    "DBHOST": db_host,
                    "DBPORT": db_port,
                    "DBNAME": db_name
                }
                

            self.save_config()

        # PostgreSQL connection string format
        self.db_config = {
            'db_username': db_username,
            'db_password': db_password,
            'db_host': db_host,
            'db_port': db_port,
            'db_name': db_name
        }
        self.connection_string = f'postgresql://{db_username}:{db_password}@{db_host}:{db_port}/{db_name}'
        self.engine = create_engine(self.connection_string)

        sample_rows_in_table_info = self.config.get('sample_rows_in_table_info') or os.environ.get('sample_rows_in_table_info')
        if sample_rows_in_table_info is None:
            sample_rows_in_table_info = prompt("Number of sample rows to be passed to model (Default is 3): ",) or 3
            self.save_config("sample_rows_in_table_info", sample_rows_in_table_info)

        sample_rows_in_table_info = int(sample_rows_in_table_info)
        self.db = SQLDatabase.from_uri(self.connection_string,sample_rows_in_table_info=sample_rows_in_table_info)

        api_key = self.config.get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY')
        if api_key is None:
            api_key = prompt("Enter your Open AI API key: ", is_password=True)
            self.save_config("OPENAI_API_KEY", api_key)

        if 'model' not in self.config:
            print("Which model do you want to use?")
            print(f"1. {GPT_MODEL3}")
            print(f"2. {GPT_MODEL4}")
            choice = prompt("(1 or 2) > ")
            if choice == "1":
                self.save_config("model", GPT_MODEL3)
            else:
                self.save_config("model", GPT_MODEL4)

        GPT_MODEL = self.config.get('model') or os.environ.get('model')
        self.llm = ChatOpenAI(model=GPT_MODEL,openai_api_key=api_key)


    def parse_args(self):
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('-help', '--help', action='help', default=argparse.SUPPRESS, help='Show this help message and exit')
        parser.add_argument('-h', '--host', type=str, required=False)
        parser.add_argument('-p', '--port', type=int, required=False)
        parser.add_argument('-U', '--username', type=str, required=False)
        parser.add_argument('-d', '--dbname', type=str, required=False)
        parser.add_argument('--password', type=str, required=False)
        return parser.parse_args()
    

    def save_config(self, key=None, value=None):
        if key and value:
            self.config[key] = value

        for k, v in self.config.items():
            if isinstance(v, datetime):
                self.config[k] = v.isoformat()

        with open(self.CONFIG_FILE, 'w') as f:
            f.write(json.dumps(self.config))


    def load_config(self):
        self.config = {}
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, 'r') as f:
                self.config = json.loads(f.read())

        for k, v in self.config.items():
            try:
                dt = datetime.fromisoformat(v)
                self.config[k] = dt
            except:
                pass


    def get_version(self):
        try:
            pyproject = toml.load(os.path.join(os.path.dirname(__file__), "..", "pyproject.toml"))
            return pyproject["tool"]["poetry"]["version"]
        except:
            return importlib.metadata.version("psqlomni")


    def chat_loop(self):
        """
        Start a chat interface loop for interacting with a database.

        This method initiates an interactive command-line session where users can input commands
        to interact with the PostgreSQL database. The available commands include displaying help
        information, showing database connection details, and querying the database. The method
        continuously prompts the user for input until the user exits the session.

        Upon receiving a command, the method processes it and provides the appropriate response.
        The Halo spinner is used to indicate that a command is being processed.

        Exceptions:
            - KeyboardInterrupt: Stops the spinner and exits the loop on a keyboard interrupt.
            - EOFError: Stops the spinner and exits the loop on an end-of-file (EOF) error.

        Returns:
            None
        """
        session = PromptSession()

        print("""
Welcome to PSQLOMNI, the chat interface to your Postgres database.
You can ask questions like:
    "help" (show some system commands)
    "show all the tables"
    "show me the first 10 rows of the users table"
        """)
        while True:
            try:
                cmd = session.prompt("\n> ")
                if cmd == "":
                    continue
                elif cmd == "help":
                    print("""
connection - show the database connection info
exit
                          """)
                    continue
                elif cmd == "connection":
                    print(f"Host: {self.db_config['db_host']}, Database: {self.db_config['db_name']}, User: {self.db_config['db_username']}")
                    print(f"Version: {self.get_version()}")
                    continue
                elif cmd == "exit":
                    return

                spinner.start("thinking...")
                self.process_command(cmd)
                spinner.stop()
            except (KeyboardInterrupt, EOFError):
                spinner.stop()
                return
    

    def process_command(self, cmd: str):

        custom_sql_query_tool = QuerySQLDataBaseTool(
                                description="Input to this tool is a detailed and correct SQL query, output is a result from the database. If the query is not correct, an error message will be returned. If an error is returned, rewrite the query, check the query, and try again. If you encounter an issue with Unknown column 'xxxx' in 'field list', use sql_db_schema to query the correct table fields.",
                                args_schema=_QuerySQLDataBaseToolInput,
                                db=self.db
                            )

        toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        context = toolkit.get_context()
        tools = toolkit.get_tools()

        try:
            query_sql_tool_name = tools[0].name
            if query_sql_tool_name == "sql_db_query":
                tools[0] = custom_sql_query_tool
        except Exception as e:
            print("An error occurred:", e)

        messages = [
            SystemMessage(
                content=(
                        """You are an agent designed to interact with a SQL database.

                            If the question does not seem related to the database, just return "I do not know" as the answer.
                            """
                )
            ),
            MessagesPlaceholder(variable_name=MEMORY_KEY),
            HumanMessagePromptTemplate.from_template("{input}"),
            AIMessage(content=SQL_FUNCTIONS_SUFFIX),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
        prompt = ChatPromptTemplate.from_messages(messages)
        prompt = prompt.partial(**context)
        llm_with_tools = self.llm.bind_tools(tools)

        agent = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: format_to_openai_tool_messages(
                    x["intermediate_steps"]
                ),
                MEMORY_KEY: lambda x: memory.load_memory_variables(x).get(MEMORY_KEY, []),
            }
            | prompt
            | llm_with_tools
            | OpenAIToolsAgentOutputParser()
        )
        
        try:
            agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory)
            result = agent_executor.invoke({"input": cmd})
            if result:
                spinner.stop()
                print(f"[Assistant] --> {result['output']}")
            else:
                print('There are no result..')
        except Exception as e:
            print(f"Error in executing agent: {e}")
            return None
            

def main():
    psqlomni = PSqlomni()
    psqlomni.chat_loop()

if __name__ == "__main__":
    main()