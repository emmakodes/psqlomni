# psqlomni

`psqlomni` is an LLM-powered chat interface for your SQL database.

It translates natural language prompts into SQL and supports multiple model providers.

## What it does

- Generates SQL for your database dialect
- Explains schema and tables
- Helps with joins, grouping, and summaries
- Lets you review SQL before execution
- Supports follow-up questions with conversation context

## Install

```bash
pip install psqlomni
```

Optional providers:

```bash
pip install "psqlomni[anthropic]"
pip install "psqlomni[google]"
pip install "psqlomni[ollama]"
pip install "psqlomni[all-models]"
```

## Run

```bash
psqlomni
```

You can also run:

```bash
python -m psqlomni
```
