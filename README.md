# psqlomni  
(psql powered with natural language)

An LLM-powered chat interface to your database. This tool understands Postgres syntax and can easily translate English queries into proper SQL queries. Uses Langchain and [Open AI](https://openai.com) model.

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

You can specify the number of sample rows that will be appended to each table description. This can increase performance as demonstrated in the paper Rajkumar et al, 2022 (https://arxiv.org/abs/2204.00498). Follows best practices as specified in: Rajkumar et al, 2022 (https://arxiv.org/abs/2204.00498)

## How it works

`psqlomni` uses Langchain and the OpenAI model to create an agent to work with your database.

When requested the LLM automatically generates the right SQL, ask if to execute the query, if yes(or y), it executes the query. The query results are then returned. If an error is returned, it rewrites the query, check the query, ask for confirmation to execute query and then try again.

### Command Reference

There are a few system commands supported for meta operations: 

`help` - show system commands

`connection` - show the current db connection details, and the active LLM model

`exit` or ctrl-c to exit

