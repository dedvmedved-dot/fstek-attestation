"""
Адаптер LLM с поддержкой:
- DeepSeek API (разработка)
- llama-server HTTP API (ваш текущий стек)
- Прямая загрузка GGUF (замкнутый контур без сервера)
"""

import os
from typing import Literal
from dotenv import load_dotenv

load_dotenv()

from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings


class LLMFactory:
    """Фабрика LLM с автоопределением провайдера из .env"""
    
    @staticmethod
    def get_llm(
        mode: Literal["reasoning", "audit", "report"] = "audit",
        temperature: float = 0.1,
        max_tokens: int = 16384,
    ) -> BaseChatModel:
        
        provider = os.getenv("LLM_PROVIDER", "deepseek")
        
        if provider == "deepseek":
            return LLMFactory._get_deepseek(mode, temperature, max_tokens)
        elif provider == "local":
            return LLMFactory._get_local(mode, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
    
    @staticmethod
    def _get_deepseek(mode: str, temperature: float, max_tokens: int) -> ChatDeepSeek:
        model = "deepseek-chat"
        if mode == "reasoning":
            model = "deepseek-reasoner"
        
        return ChatDeepSeek(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            timeout=120,
            max_retries=3,
        )
    
    @staticmethod
    def _get_local(mode: str, temperature: float, max_tokens: int) -> ChatOpenAI:
        """Подключение к llama-server (совместим с OpenAI API)"""
        server_url = os.getenv("LLAMA_SERVER_URL", "http://192.168.0.210:8080/v1")
        
        return ChatOpenAI(
            model="local-model",  # Имя не важно, llama-server игнорирует
            base_url=server_url,
            api_key="not-needed",
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=300,
            max_retries=3,
        )
    
    

    @staticmethod
    def get_embeddings() -> Embeddings:
        """Эмбеддинги: локальные Ollama (без региональных ограничений)"""
        from langchain_community.embeddings import OllamaEmbeddings
        return OllamaEmbeddings(
            model="nomic-embed-text",
            base_url="http://localhost:11434",
        )

    @staticmethod
    def get_llm_usage_stats() -> dict:
        """Получить статистику использования"""
        provider = os.getenv("LLM_PROVIDER", "deepseek")
        return {
            "provider": provider,
            "model": "deepseek-chat" if provider == "deepseek" else "local-model",
            "temperature": 0.1,
        }


# Быстрый тест при запуске файла напрямую
if __name__ == "__main__":
    print(f"Провайдер: {os.getenv('LLM_PROVIDER', 'deepseek')}")
    
    llm = LLMFactory.get_llm(mode="audit")
    print(f"LLM: {type(llm).__name__}")
    
    embeddings = LLMFactory.get_embeddings()
    print(f"Embeddings: {type(embeddings).__name__}")
    
    # Тестовый вызов
    response = llm.invoke("Скажи 'Привет, ФСТЭК!' одним предложением.")
    print(f"Ответ: {response.content}")
