# psqlomni

Natural language chat for your SQL database.

[![Build](https://img.shields.io/github/actions/workflow/status/emmakodes/psqlomni/release.yml?job=build&label=build)](https://github.com/emmakodes/psqlomni/actions/workflows/release.yml)
[![Test](https://img.shields.io/github/actions/workflow/status/emmakodes/psqlomni/ci.yml?branch=main&job=test&label=test)](https://github.com/emmakodes/psqlomni/actions/workflows/ci.yml)
[![Publish](https://img.shields.io/github/actions/workflow/status/emmakodes/psqlomni/release.yml?job=publish&label=publish)](https://github.com/emmakodes/psqlomni/actions/workflows/release.yml)

`psqlomni` translates plain English into SQL and runs it against your database.

It supports SQLAlchemy-compatible databases and multiple model providers:

- OpenAI
- Anthropic
- Google Gemini
- Ollama

## Demo Video

Add your project demo video here:

- `TODO: Replace this with your demo link`
- Example: `https://github.com/<org>/<repo>/assets/<video-id>`

## Install

```bash
pip install psqlomni
```

Optional provider extras:

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

Or from source:

```bash
python -m psqlomni
```

## Quick Setup

Set either a full DB URI (recommended) or individual DB fields.

### Option 1: Full DB URI (recommended)

```bash
export DB_URI="postgresql+psycopg2://user:password@host:5432/dbname"
```

### Option 2: Individual DB Fields

```bash
export DBDIALECT="postgresql"
export DBHOST="localhost"
export DBPORT="5432"
export DBNAME="mydb"
export DBUSER="myuser"
export DBPASSWORD="mypassword"
```

### Model Provider

```bash
export MODEL_PROVIDER="openai"
export MODEL="gpt-4o-mini"
export OPENAI_API_KEY="your-key"
```

When values are missing, `psqlomni` prompts you interactively.

## What It Does

- Converts natural language prompts into SQL
- Shows SQL for approval before execution
- Lets you edit SQL before running it
- Retries when SQL fails, then asks for approval again
- Keeps conversation history for follow-up questions
- Supports a normal mode and a verbose trace mode

## Useful Commands

- `/help` - list commands
- `/connection` - show active DB and model
- `/connect` - connect to another database
- `/mode normal|verbose` - switch output detail
- `/provider` - show or set provider
- `/model` - show or set model
- `/new` - start a new thread
- `/resume <thread_id>` - resume a thread
- `/exit` - quit

## Safety

Every generated SQL query requires your approval before execution.

## Docs

- [Contributing](CONTRIBUTING.md)
- [Releasing](RELEASING.md)
- [Security](SECURITY.md)
- [Project docs](docs/)
