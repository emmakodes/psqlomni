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
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent
from typing import Any
import subprocess

GPT_MODEL3="gpt-3.5-turbo-0125" # "gpt-3.5-turbo-1106"
GPT_MODEL4="gpt-4-1106-preview"

# Replace these with your specific database credentials

class PSqlomni:
    CONFIG_FILE = os.path.expanduser('~/.psqlomni')

    def __init__(self) -> None:
        self.load_config()
        self.llm:ChatOpenAI
        self.db: SQLDatabase = None
        self.spinned_up_db_name:str
        self.container_name:str

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
                print(f"host={db_host} dbname={db_name} user={db_username} password={db_password}")
                try:
                    pgconn = psycopg2.connect(
                        f"host={db_host} dbname={db_name} user={db_username} password={db_password}",
                        connect_timeout=10
                    )
                    with pgconn.cursor() as cursor:
                        cursor.execute("SELECT version();")
                    connection_good = True
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

        # still iterating other options for below process 
        print('Setting up Docker to spin up isolated instances of the database')
        if not self.is_postgres_image_pulled():
            print("PostgreSQL Docker image is not pulled. Pulling now...")
            subprocess.run(['docker', 'pull', 'postgres'])
        else:
            print("PostgreSQL Docker image is already pulled.")

        # Run PostgreSQL container
        self.container_name = 'my_postgres_db_x3F9k2PqY_5tRzU1'
        self.spinned_up_db_name = f'{db_name}_x3F9k2PqY_5tRzU1'
        spinned_up_db_username = db_username
        spinned_up_db_password = db_password
        spinned_up_port_number = 5433 
        spinned_up_db_host = 'localhost'

        print(f'running {self.container_name} container')
        subprocess.run(['docker', 'run', '--name', self.container_name, '-e', f'POSTGRES_DB={self.spinned_up_db_name}', '-e', f'POSTGRES_USER={spinned_up_db_username}', '-e', f'POSTGRES_PASSWORD={spinned_up_db_password}', '-d', '-p', f'{spinned_up_port_number}:5432', 'postgres'])
        print('dumping data')
        print('Enter your database password')
        # Dump data from original database
        subprocess.run(['pg_dump', '-U', db_username, '-d', db_name, '-h', db_host, '-Fc', '-f', f'backup_{self.spinned_up_db_name}.dump'])
        print(f'copying dump to {self.container_name}:backup_{self.spinned_up_db_name}.dump')
        # Copy dump file into Docker container
        subprocess.run(['docker', 'cp', f'backup_{self.spinned_up_db_name}.dump', f'{self.container_name}:backup_{self.spinned_up_db_name}.dump'])
        print('restoring dump')
        # Restore data in Docker container
        subprocess.run(['docker', 'exec', '-it', self.container_name, 'bash', '-c', f'pg_restore -U $POSTGRES_USER -d $POSTGRES_DB /backup_{self.spinned_up_db_name}.dump'], env={'POSTGRES_USER': spinned_up_db_username, 'POSTGRES_DB': self.spinned_up_db_name})

        # PostgreSQL connection string format
        self.db_config = {
            'db_username': spinned_up_db_username,
            'db_password': spinned_up_db_password,
            'db_host': spinned_up_db_host,
            'db_port': spinned_up_port_number,
            'db_name': self.spinned_up_db_name
        }
        self.connection_string = f'postgresql://{spinned_up_db_username}:{spinned_up_db_password}@{spinned_up_db_host}:{spinned_up_port_number}/{self.spinned_up_db_name}'

        self.engine = create_engine(self.connection_string)
        print(f'connecting to spinned up db: {self.spinned_up_db_name}')

        self.db = SQLDatabase.from_uri(self.connection_string)
        print('connected')
        api_key = self.config.get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY')
        if api_key is None:
            api_key = prompt("Enter your Open AI API key: ", is_password=True)
            self.save_config("OPENAI_API_KEY", api_key)

        if 'model' not in self.config:
            print("Which model do you want to use?")
            print(f"1. {GPT_MODEL3}")
            print(f"2. {GPT_MODEL4}")
            choice = prompt("(1 or 2) >")
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
        session = PromptSession()

        spinner = Halo(text='thinking', spinner='dots')
        self.spinner = spinner

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
history - show the complete message history
new thread - start a new thread
exit
                          """)
                    continue
                elif cmd == "connection":
                    print(f"Host: {self.db_config['db_host']}, Database: {self.db_config['db_name']}, User: {self.db_config['db_username']}")
                    print(f"Version: {self.get_version()}")
                    continue
                elif cmd == "exit":
                    self.remove_container_and_data(self.container_name,self.spinned_up_db_name)
                    return

                cmd = cmd
                spinner.start("thinking...")
                self.process_command(cmd)
                spinner.stop()
            except (KeyboardInterrupt, EOFError):
                spinner.stop()
                self.remove_container_and_data(self.container_name,self.spinned_up_db_name)
                return
    

    def remove_container_and_data(self, container_name, db_name):
        # Check if the container is running
        result = subprocess.run(['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}'], capture_output=True, text=True)
        
        if container_name in result.stdout.splitlines():
            # Container is running, stop it first
            subprocess.run(['docker', 'stop', container_name])
            print(f"Container {container_name} stopped.")
            
            # Remove the container
            subprocess.run(['docker', 'rm', container_name])
            print(f"Container {container_name} removed.")
        else:
            # Check if the container exists but is not running
            result = subprocess.run(['docker', 'ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Names}}'], capture_output=True, text=True)
            
            if container_name in result.stdout.splitlines():
                # Container exists but is not running, remove it
                subprocess.run(['docker', 'rm', container_name])
                print(f"Container {container_name} removed.")
            else:
                print(f"Container {container_name} does not exist.")

        # Delete the dumped data file if it exists
        if os.path.exists(f'backup_{db_name}.dump'):
            os.remove(f'backup_{db_name}.dump')
            print("Dumped data file deleted.")
        else:
            print("Dumped data file not found.")
    
    def is_postgres_image_pulled(self):
        # Run the command to list Docker images
        result = subprocess.run(['docker', 'images', '--format', '{{.Repository}}'], capture_output=True, text=True)
        
        # Check if 'postgres' is in the output
        return 'postgres' in result.stdout.splitlines()

    
    def process_command(self, cmd: str):
        # agent_executor = create_sql_agent(self.llm, db=self.db, agent_type="openai-tools", verbose=True)
        agent_executor = create_sql_agent(self.llm, db=self.db, agent_type="openai-tools")
        result = agent_executor.invoke(
            {
                "input": cmd
            }
        )
        # print('result',result)
        if result and 'output' in result and result['output'] is not None:
            print(result['output'])


def main():
    psqlomni = PSqlomni()
    psqlomni.chat_loop()

if __name__ == "__main__":
    main()