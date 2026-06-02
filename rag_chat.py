"""
RAG-чат с поддержкой нескольких LLM-провайдеров, режимов DeepThink/Instant/Expert,
загрузкой файлов и семантическим поиском по базе НПА.
"""

import os
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI
from chromadb import HttpClient
from chromadb.config import Settings
from llm_adapter import LLMFactory


class RAGChat:
    PROVIDERS = {
        "deepseek": {
            "name": "DeepSeek",
            "models": {
                "deepseek-chat": "DeepSeek V3 (Instant)",
                "deepseek-reasoner": "DeepSeek R1 (DeepThink)",
            },
            "base_url": "https://api.deepseek.com",
            "api_key_env": "DEEPSEEK_API_KEY",
        },
        "openai": {
            "name": "ChatGPT (OpenAI)",
            "models": {
                "gpt-4o": "GPT-4o",
                "gpt-4o-mini": "GPT-4o Mini",
                "o1-mini": "o1-mini (Reasoning)",
            },
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "OPENAI_API_KEY",
        },
        "perplexity": {
            "name": "Perplexity",
            "models": {
                "sonar-pro": "Sonar Pro (Online)",
                "sonar": "Sonar (Online)",
            },
            "base_url": "https://api.perplexity.ai",
            "api_key_env": "PERPLEXITY_API_KEY",
        },
        "local": {
            "name": "Локальная модель (Ollama)",
            "models": {
                "qwen2.5:32b": "Qwen2.5 32B",
                "deepseek-coder-v2:16b": "DeepSeek Coder 16B",
            },
            "base_url": "http://localhost:11434/v1",
            "api_key_env": None,
        },
    }

    def __init__(self):
        self.chroma_client = HttpClient(
            host="localhost", port=8001,
            settings=Settings(anonymized_telemetry=False),
        )
        self.embeddings = LLMFactory.get_embeddings()
        self.collection = self.chroma_client.get_collection("fstek_npa")
        self.chat_history: List[Dict] = []
        self._doc_cache = {}  # Кэш чанков документов
        self._last_opened_doc = None  # Последний открытый документ

    def get_all_sources(self) -> List[str]:
        try:
            count = self.collection.count()
            results = self.collection.get(limit=count)
            sources = set()
            for meta in results.get("metadatas", []):
                src = meta.get("source", "")
                if src:
                    sources.add(src)
            return sorted(sources)
        except:
            return []

    def search_keywords(self, query: str) -> List[Dict]:
        """Поиск по ключевым словам во всех документах"""
        try:
            count = self.collection.count()
            results = self.collection.get(limit=count)
            
            # Разбиваем запрос на ключевые слова (от 4 букв)
            keywords = [w.lower() for w in query.split() if len(w) >= 4]
            
            scored = []
            for doc, meta in zip(results.get("documents", []), results.get("metadatas", [])):
                text_lower = doc.lower()
                score = sum(1 for kw in keywords if kw in text_lower)
                if score > 0:
                    scored.append((score, {
                        "text": doc,
                        "source": meta.get("source", "unknown"),
                        "paragraph_id": meta.get("paragraph_id", ""),
                    }))
            
            # Сортируем по релевантности
            scored.sort(key=lambda x: x[0], reverse=True)
            return [s[1] for s in scored[:30]]
        except:
            return []
    
    def hybrid_search(self, query: str, n_results: int = 30) -> List[Dict]:
        """Гибридный поиск: семантический + ключевые слова"""
        semantic = self.search_npa(query, n_results)
        keyword = self.search_keywords(query)
        
        # Объединяем, убирая дубликаты
        seen = set()
        combined = []
        for doc in keyword + semantic:  # keyword first — точные совпадения приоритетнее
            key = (doc["source"], doc["paragraph_id"])
            if key not in seen:
                seen.add(key)
                combined.append(doc)
        
        return combined[:n_results * 2]  # Больше результатов
    
    def search_npa(self, query: str, n_results: int = 30) -> List[Dict]:
        try:
            qe = self.embeddings.embed_query(query)
            results = self.collection.query(query_embeddings=[qe], n_results=n_results)
            docs = []
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                docs.append({
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "paragraph_id": meta.get("paragraph_id", ""),
                })
            return docs
        except Exception as e:
            return [{"text": f"Ошибка: {e}", "source": "error", "paragraph_id": ""}]

    def search_by_document(self, doc_name: str) -> List[Dict]:
        """Поиск всех параграфов из конкретного документа"""
        try:
            count = self.collection.count()
            results = self.collection.get(limit=count)
            docs = []
            for doc, meta in zip(results.get("documents", []), results.get("metadatas", [])):
                if meta.get("source", "").lower() == doc_name.lower():
                    docs.append({
                        "text": doc,
                        "source": meta.get("source", ""),
                        "paragraph_id": meta.get("paragraph_id", ""),
                    })
            return docs
        except:
            return []
    
    def _get_client(self, provider: str):
        config = self.PROVIDERS[provider]
        if provider == "local":
            return OpenAI(base_url=config["base_url"], api_key="not-needed")
        api_key = os.getenv(config["api_key_env"])
        if not api_key:
            raise ValueError(f"API-ключ для {config['name']} не задан. Установите {config['api_key_env']} в .env")
        return OpenAI(base_url=config["base_url"], api_key=api_key)

    def _read_file(self, file_path: str) -> Optional[str]:
        path = Path(file_path)
        suffix = path.suffix.lower()
        try:
            if suffix == ".pdf":
                from pypdf import PdfReader
                reader = PdfReader(file_path)
                return "\n".join(teletype.extractText(p) for p in all_p[:200])
            elif suffix == ".docx":
                import docx2txt
                return docx2txt.process(file_path)
            elif suffix == ".xlsx":
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True)
                text = []
                for sheet in wb.sheetnames[:3]:
                    ws = wb[sheet]
                    text.append(f"\n=== Лист: {sheet} ===")
                    for row in ws.iter_rows(values_only=True):
                        text.append(" | ".join(str(c) if c else "" for c in row))
                return "\n".join(text[:200])
            elif suffix == ".odt":
                from odf.opendocument import load as odf_load
                from odf import text as odf_text, teletype
                doc = odf_load(file_path)
                all_p = doc.getElementsByType(odf_text.P)
                return "\n".join(teletype.extractText(p) for p in all_p[:200])
            elif suffix in [".md", ".txt"]:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            elif suffix == ".json":
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.dumps(json.load(f), ensure_ascii=False, indent=2)
            else:
                return f"[Неподдерживаемый формат: {suffix}]"
        except Exception as e:
            return f"[Ошибка чтения: {e}]"

    def chat(self, message: str, provider: str = "deepseek", model: str = "deepseek-chat",
             files: List[str] = None, system_prompt: str = None) -> Dict:
        
        # Получаем ВСЕ источники
        all_sources = self.get_all_sources()
        doc_pagination = None
        sources_list = "\n".join(f"- {s}" for s in all_sources)
        
        # Определяем тип вопроса
        ask_about_sources = any(w in message.lower() for w in [
            "какие документы", "какие нпа", "состав базы", "что в базе",
            "какие нормативные", "перечень документов", "список нпа",
            "сколько документов", "документы в базе", "документов в базе"
        ])
        
        open_doc_request = None
        # Определяем, спрашивают ли про конкретный документ
        doc_by_name = None
        msg_lower = message.lower()
        for source in all_sources:
            if source.lower() in msg_lower:
                doc_by_name = source
                break

        if doc_by_name:
            for word in ["открой", "выведи", "покажи", "прочитай", "зачитай", "раскрой", "продолжи", "следующая", "дальше"]:
                if word in msg_lower:
                    open_doc_request = doc_by_name
                    self._last_opened_doc = doc_by_name
                    print(f"DEBUG: open_doc_request={open_doc_request}")
                    break
        
        # Если команда "продолжи" без имени документа — используем последний открытый
        if not open_doc_request and not doc_by_name:
            for word in ["продолжи", "следующая", "дальше"]:
                if word in msg_lower and self._last_opened_doc:
                    open_doc_request = self._last_opened_doc
                    doc_by_name = self._last_opened_doc
                    print(f"DEBUG: продолжаем {open_doc_request}")
                    break

        # Поиск в НПА
        if ask_about_sources:
            npa_docs = []
        elif doc_by_name and any(w in msg_lower for w in ["открой", "продолжи", "выведи", "покажи", "следующая", "дальше"]):
            open_doc_request = doc_by_name
            doc_pagination = self.get_document_paginated(open_doc_request)
            npa_docs = [{"text": c["text"], "source": open_doc_request, "paragraph_id": c["paragraph_id"]} for c in doc_pagination["chunks"]]
        elif open_doc_request:
            doc_pagination = self.get_document_paginated(open_doc_request)
            npa_docs = [{"text": c["text"], "source": open_doc_request, "paragraph_id": c["paragraph_id"]} for c in doc_pagination["chunks"]]
        else:
            npa_docs = self.search_npa(message)
        
        # Чтение файлов
        file_contents = []
        if files:
            for fp in files:
                content = self._read_file(fp)
                if content:
                    file_contents.append({"name": Path(fp).name, "content": content[:3000]})
        # Формируем системный промпт
        if system_prompt is None:
            pass  # filled below
            if ask_about_sources:
                system_prompt = "AI assistant. List all " + str(len(all_sources)) + " documents in the database:\n" + sources_list
            elif open_doc_request and doc_pagination:
                total = doc_pagination["total_chunks"]
                page = doc_pagination["page"]
                ctx = "Document: " + str(open_doc_request) + "\nPage " + str(page) + "/" + str((total-1)//20 + 1) + "\n\n"
                for j, doc in enumerate(npa_docs, 1):
                    ctx += doc['text'][:2000] + "\n\n"
                if doc_pagination["has_next"]:
                    ctx += "---\nShown " + str(len(npa_docs)) + " of " + str(total) + ". Continue: continue " + str(open_doc_request) + "\n"
                system_prompt = "You are a document viewer. Output the text below EXACTLY as provided, without any changes, summaries, or additions. Copy verbatim:\n\n" + ctx
            elif npa_docs:
                ctx = "Search results (" + str(len(npa_docs)) + " chunks):\n\n"
                for j, doc in enumerate(npa_docs[:20], 1):
                    ctx += "[" + str(doc['source']) + "] " + doc['text'][:2000] + "\n\n"
                system_prompt = "You are an AI assistant with NPA database. Use ONLY the context below.\n\n" + sources_list + "\n\n" + ctx
            else:
                system_prompt = "You are an AI assistant with NPA database (" + str(len(all_sources)) + " docs). Answer based on the context."

                if file_contents:
                    file_context = "\n\n## ЗАГРУЖЕННЫЕ ФАЙЛЫ\n"
                    for fc in file_contents:
                        file_context += f"\n### {fc['name']}\n{fc['content'][:500]}\n"
                
                system_prompt = f"""Ты - AI-ассистент, который отвечает СТРОГО на основе предоставленной базы нормативно-правовых актов.

## ПОЛНЫЙ ПЕРЕЧЕНЬ НПА В БАЗЕ ({len(all_sources)} документов):
{sources_list}
{npa_context}
{file_context}

ПРАВИЛА:
1. Используй ТОЛЬКО документы из перечня выше. Не ссылайся на приказы №17, №31, №55 и другие, если их нет в списке.
2. Если в найденных требованиях есть ответ — цитируй их с указанием документа и пункта.
3. Если ответа нет — честно скажи об этом и предложи обратиться к документам из перечня.
4. Отвечай на русском языке, профессионально."""
        
        # Отправка
        client = self._get_client(provider)
        messages = [{"role": "system", "content": system_prompt}]
        for msg in self.chat_history[-10:]:
            messages.append(msg)
        messages.append({"role": "user", "content": message})
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7 if provider != "deepseek" else None,
                max_tokens=4096,
            )
            reply = response.choices[0].message.content
            self.chat_history.append({"role": "user", "content": message})
            self.chat_history.append({"role": "assistant", "content": reply})
            return {
                "reply": reply,
                "context": npa_docs,
                "files": file_contents,
                "model": model,
                "provider": provider,
            }
        except Exception as e:
            return {
                "reply": f"❌ Ошибка: {e}",
                "context": npa_docs,
                "files": file_contents,
                "model": model,
                "provider": provider,
            }

    def get_document_paginated(self, doc_name: str, page: int = 1, page_size: int = 20) -> dict:
        """Получить содержимое документа постранично с кэшированием"""
        if doc_name not in self._doc_cache:
            self._doc_cache[doc_name] = self.search_by_document(doc_name)
        docs = self._doc_cache[doc_name]
        total = len(docs)
        start = (page - 1) * page_size
        end = min(start + page_size, total)
        
        chunks = []
        for doc in docs[start:end]:
            chunks.append({
                "paragraph_id": doc["paragraph_id"],
                "text": doc["text"][:2000],
            })
        
        return {
            "doc_name": doc_name,
            "total_chunks": total,
            "page": page,
            "page_size": page_size,
            "has_next": end < total,
            "has_prev": page > 1,
            "chunks": chunks,
        }
    
    def clear_history(self):
        self.chat_history = []
        self._doc_cache = {}

    def get_history(self) -> List[Dict]:
        return self.chat_history
