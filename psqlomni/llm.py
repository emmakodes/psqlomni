from langchain_openai import ChatOpenAI

from psqlomni.config import AppConfig


def build_llm(config: AppConfig) -> ChatOpenAI:
    return ChatOpenAI(model=config.model, api_key=config.openai_api_key)
