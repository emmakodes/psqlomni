from psqlomni.config import AppConfig


def _missing_dependency_message(provider: str, package: str) -> str:
    return (
        f"{provider} support requires optional dependency `{package}`. "
        f"Install with `pip install psqlomni[{provider}]`."
    )


def build_llm(config: AppConfig):
    provider = config.model_provider

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "OpenAI support requires `langchain-openai`. Install with `pip install psqlomni`."
            ) from exc
        return ChatOpenAI(model=config.model, api_key=config.openai_api_key)

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(_missing_dependency_message("anthropic", "langchain-anthropic")) from exc
        return ChatAnthropic(model=config.model, api_key=config.anthropic_api_key)

    if provider == "google_gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(_missing_dependency_message("google", "langchain-google-genai")) from exc
        return ChatGoogleGenerativeAI(model=config.model, google_api_key=config.google_api_key)

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(_missing_dependency_message("ollama", "langchain-ollama")) from exc
        return ChatOllama(model=config.model, base_url=config.ollama_base_url)

    raise ValueError(f"Unsupported model provider: {provider}")
