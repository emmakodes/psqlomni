# Getting Started

## Requirements

- Database credentials
- API key for your model provider

## Database configuration

You can configure the database with:

- `DB_URI` (recommended), or
- structured fields: `DBDIALECT`, `DBHOST`, `DBNAME`, `DBUSER`, `DBPASSWORD`, `DBPORT`

CLI flags include:

- `--db-uri`
- `--db-dialect`
- `-h`, `-p`, `-U`, `-d`, `--password`

## Model configuration

Set:

- `MODEL_PROVIDER` (`openai|anthropic|google_gemini|ollama`)
- `MODEL` (provider model id)
- provider API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`)
- `OLLAMA_BASE_URL` (default `http://localhost:11434`)

## First run

At first launch, `psqlomni` prompts for missing DB/model settings and stores them in `~/.psqlomni`.

Delete `~/.psqlomni` to reset setup.
