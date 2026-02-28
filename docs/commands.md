# Commands

Use `/` to open the command palette.

## Core commands

- `/help` show system commands
- `/connection` show current DB/provider/model/thread info
- `/disconnect` disconnect from the current database
- `/connect` connect to another database interactively
- `/mode normal|verbose` switch output detail
- `/provider` show current provider
- `/provider <name>` set provider (`openai|anthropic|google_gemini|ollama`)
- `/model` show current model and open model picker
- `/model list` list known models for current provider
- `/model <name>` set model directly
- `/new` start a new thread
- `/resume <thread_id>` resume an earlier in-memory thread
- `/exit` or `ctrl-c` exit

Legacy forms such as `help`, `connection`, `mode ...`, and `exit` still work.
