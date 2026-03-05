from psqlomni.config import AppConfig


class MissingProviderDependencyError(RuntimeError):
    def __init__(self, provider: str, package: str, install_extra: str):
        self.provider = provider
        self.package = package
        self.install_extra = install_extra
        super().__init__(_missing_dependency_message(install_extra, package))


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
            raise MissingProviderDependencyError("anthropic", "langchain-anthropic", "anthropic") from exc
        return ChatAnthropic(model=config.model, api_key=config.anthropic_api_key)

    if provider == "google_gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:  # pragma: no cover
            raise MissingProviderDependencyError("google_gemini", "langchain-google-genai", "google") from exc
        return ChatGoogleGenerativeAI(model=config.model, google_api_key=config.google_api_key)

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:  # pragma: no cover
            raise MissingProviderDependencyError("ollama", "langchain-ollama", "ollama") from exc
        return ChatOllama(model=config.model, base_url=config.ollama_base_url)

    raise ValueError(f"Unsupported model provider: {provider}")
