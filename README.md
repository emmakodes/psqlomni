# psqlomni  
(psql powered with natural language)

An LLM-powered chat interface to your database. This tool understands Postgres syntax and can translate English prompts into SQL. It uses a LangGraph + LangChain SQL agent and supports OpenAI, Anthropic, Google Gemini, and Ollama.

This provides the quickest way to enable LLM chat with your data - no preparation is needed.


Here's a quick demo showing natural language queries:

https://github.com/emmakodes/psqlomni/assets/34986076/0c58f4fd-c359-47c2-8e3c-4b068545e522

## Installation

You will need:

1. credentials for your database
2. credentials for your selected model provider.

then

```
pip install psqlomni
```

Install optional providers only when needed:

```bash
pip install "psqlomni[anthropic]"
pip install "psqlomni[google]"
pip install "psqlomni[ollama]"
pip install "psqlomni[all-models]"
```

or download the source. 

Run the CLI with:

    psqlomni

or use `python -m psqlomni` to run from source.

## What can it do?

The model understands most Postgres syntax, so it can generate both generic SQL commands as well as very Postgres-specific ones like querying system settings. It can answer questions based on the databases' schema as well as on the databases' content (like describing a specific table).

The LLM is also good at analyzing tables, understanding what they are likely used for, and inferring relationships between tables. It is good at writing JOINs between tables without explicit instruction.

It can write queries to group and summarize results.

It can recover from errors by running a generated query, catching the traceback and regenerating it correctly.

It will save tokens by only retrieving the schema from relevant tables.

It also maintains a history of the chat, so you can easily ask follow up questions.

### Configuration

You can configure the database connection either using `psql` style command line arguments
or the env vars `DBHOST`, `DBNAME`, `DBUSER`, `DBPASSWORD`, `DBPORT`.

Model configuration is controlled with:

- `MODEL_PROVIDER` (`openai|anthropic|google_gemini|ollama`)
- `MODEL` (provider model id)
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`
- `OLLAMA_BASE_URL` (for local models, default `http://localhost:11434`)

When you first run the program it prompts for missing DB and provider credentials.

After first setup all the configuration information is stored in `~/.psqlomni`. Delete that
file if you want to start over.

You can specify the number of sample rows that will be appended to each table description. This can increase performance as demonstrated in the paper [Rajkumar et al, 2022](https://arxiv.org/abs/2204.00498). Follows best practices as specified in: [Rajkumar et al, 2022](https://arxiv.org/abs/2204.00498)

## How it works

`psqlomni` uses a LangGraph SQL agent flow with explicit tool nodes:

- table discovery tool node
- schema tool node
- query tool node

Every generated SQL query is paused by an interrupt before execution. You can:

- accept and run the query
- edit the SQL and run the edited query
- send feedback without execution
- cancel execution

If an error is returned, the agent can revise the query and request approval again.

### Command Reference

There are a few system commands supported for meta operations: 

`/` - open an arrow-key command palette and press enter to run a command

`/help` - show system commands

`/connection` - show current db connection, active provider/model, output mode, and thread id

`/disconnect` - disconnect from the current database

`/connect` - connect to a different database (interactive prompts)

`/mode normal|verbose` - switch between compact output and full process tracing

`/provider` - show current provider

`/provider <name>` - set provider for current session (`openai|anthropic|google_gemini|ollama`)

`/model` - show current model and open model picker for current provider

`/model list` - print known models for current provider

`/model <name>` - set model directly (use this for models not in the built-in list)

`/new` - start a new thread

`/resume <thread_id>` - resume a prior in-memory thread from this session

`/exit` or ctrl-c - exit

Legacy forms (`help`, `connection`, `mode ...`, `exit`) still work.

For Ollama, use a local model that supports tool calling. The built-in Ollama list includes tool-capable open models.

### Output Stages

In verbose mode, each turn is labeled so the process is easy to follow:

- `[USER]` - your prompt
- `[AGENT]` - planning state before tool calls
- `[TOOL CALL]` - tool selected with arguments
- `[TOOL RESULT:<name>]` - result returned by the tool
- `[APPROVAL REQUIRED]` - SQL that must be accepted/edited/cancelled before execution
- `[FINAL]` - final assistant response
