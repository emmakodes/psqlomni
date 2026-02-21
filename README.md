# psqlomni  
(psql powered with natural language)

An LLM-powered chat interface to your database. This tool understands Postgres syntax and can translate English prompts into SQL. It now uses LangGraph + LangChain with an OpenAI chat model.

This provides the quickest way to enable LLM chat with your data - no preparation is needed.


Here's a quick demo showing natural language queries:

https://github.com/emmakodes/psqlomni/assets/34986076/0c58f4fd-c359-47c2-8e3c-4b068545e522

## Installation

You will need:

1. credentials for your database
2. an OpenAI [API Key](https://platform.openai.com/account/api-keys) from your OpenAI account.

then

```
pip install psqlomni
```

or download the source. 

Run the CLI with:

    psqlomni

or use `python -m psqlomni` to run from source.

## What can it do?

The Open AI model understands most Postgres syntax, so it can generate both generic SQL commands as well as very Postgres-specific ones like querying system settings. It can answer questions based on the databases' schema as well as on the databases' content (like describing a specific table).

The LLM is also good at analyzing tables, understanding what they are likely used for, and inferring relationships between tables. It is good at writing JOINs between tables without explicit instruction.

It can write queries to group and summarize results.

It can recover from errors by running a generated query, catching the traceback and regenerating it correctly.

It will save tokens by only retrieving the schema from relevant tables.

It also maintains a history of the chat, so you can easily ask follow up questions.

### Configuration

You can configure the database connection either using `psql` style command line arguments
or the env vars `DBHOST`, `DBNAME`, `DBUSER`, `DBPASSWORD`, `DBPORT`.

Else when you first run the program it will prompt you for the connection credentials as
well as your OpenAI API key.

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

`/connection` - show current db connection, active model, output mode, and thread id

`/disconnect` - disconnect from the current database

`/connect` - connect to a different database (interactive prompts)

`/mode normal|verbose` - switch between compact output and full process tracing

`/model` - show current model

`/model <name>` - set model for current session

`/new` - start a new thread

`/resume <thread_id>` - resume a prior in-memory thread from this session

`/exit` or ctrl-c - exit

Legacy forms (`help`, `connection`, `mode ...`, `exit`) still work.

### Output Stages

In verbose mode, each turn is labeled so the process is easy to follow:

- `[USER]` - your prompt
- `[AGENT]` - planning state before tool calls
- `[TOOL CALL]` - tool selected with arguments
- `[TOOL RESULT:<name>]` - result returned by the tool
- `[APPROVAL REQUIRED]` - SQL that must be accepted/edited/cancelled before execution
- `[FINAL]` - final assistant response
