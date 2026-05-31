"""
Загрузчик НПА ФСТЭК с иерархическим чанкингом.
Разбивает PDF по пунктам требований, индексирует в ChromaDB.
"""

import os
import re
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

from langchain_community.document_loaders import PyPDFLoader
from chromadb import HttpClient
from chromadb.config import Settings

from llm_adapter import LLMFactory


class NPALoader:
    """Загрузчик нормативно-правовых актов в векторную БД"""

    def __init__(self):
        chroma_host = os.getenv("CHROMA_HOST", "localhost")
        chroma_port = int(os.getenv("CHROMA_PORT", "8001"))

        self.chroma_client = HttpClient(
            host=chroma_host,
            port=chroma_port,
            settings=Settings(anonymized_telemetry=False),
        )
        self.embeddings = LLMFactory.get_embeddings()

    def create_collection(self, name: str = "fstek_npa"):
        """Создать или пересоздать коллекцию"""
        try:
            self.chroma_client.delete_collection(name)
            print(f"🗑️  Старая коллекция '{name}' удалена")
        except:
            pass

        collection = self.chroma_client.create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
        print(f"✅ Коллекция '{name}' создана")
        return collection

    def extract_paragraphs(self, text: str, doc_name: str) -> List[Dict]:
        """
        Извлечение параграфов из текста НПА.
        Ищет паттерны ФСТЭК (РСБ.4, АУД.1) и обычную нумерацию.
        """
        paragraphs = []

        # Паттерн для идентификаторов ФСТЭК
        fstek_pattern = r'(?:^|\n)([А-Я]{2,4}\.\d{1,2}[\.\d]*)\s+(.*?)(?=\n[А-Я]{2,4}\.\d|\n\n\n|\Z)'

        matches = re.finditer(fstek_pattern, text, re.DOTALL | re.MULTILINE)
        for match in matches:
            para_id = match.group(1).strip()
            para_text = re.sub(r'\s+', ' ', match.group(2).strip())

            if len(para_text) > 50:
                paragraphs.append({
                    "id": f"{doc_name}::{para_id}_{len(paragraphs)}",
                    "paragraph_id": para_id,
                    "text": para_text,
                    "source": doc_name,
                })

        # Если нет FSTEC-идентификаторов, ищем обычную нумерацию
        if not paragraphs:
            num_pattern = r'(?:^|\n)(\d+\.\d+(?:\.\d+)?)\s+(.*?)(?=\n\d+\.\d|\n\n\n|\Z)'
            matches = re.finditer(num_pattern, text, re.DOTALL | re.MULTILINE)
            for match in matches:
                para_id = match.group(1).strip()
                para_text = re.sub(r'\s+', ' ', match.group(2).strip())

                if len(para_text) > 50:
                    paragraphs.append({
                        "id": f"{doc_name}::{para_id}_{len(paragraphs)}",
                        "paragraph_id": para_id,
                        "text": para_text,
                        "source": doc_name,
                    })

        return paragraphs

    def load_pdf(self, pdf_path: str) -> List[Dict]:
        """Загрузка PDF и извлечение параграфов"""
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()

        doc_name = Path(pdf_path).stem
        full_text = "\n\n".join([p.page_content for p in pages])

        # Очистка артефактов PDF
        full_text = re.sub(r'(\w)-\n(\w)', r'\1\2', full_text)
        full_text = re.sub(r'\n{3,}', '\n\n', full_text)

        return self.extract_paragraphs(full_text, doc_name)

    def _add_documents_safe(self, collection, ids, documents, metadatas, pdf_name):
        """Безопасное добавление документов с разбивкой длинных"""
        max_chars = 2000
        batch_size = 50

        chunked_ids = []
        chunked_docs = []
        chunked_meta = []

        for i, doc in enumerate(documents):
            if len(doc) <= max_chars:
                chunked_ids.append(f"{ids[i]}_ch0")
                chunked_docs.append(doc)
                chunked_meta.append(metadatas[i])
            else:
                for j, start in enumerate(range(0, len(doc), max_chars)):
                    chunk = doc[start:start + max_chars]
                    chunked_ids.append(f"{ids[i]}_ch{j}")
                    chunked_docs.append(chunk)
                    chunked_meta.append({**metadatas[i], "chunk": j})

        total_batches = (len(chunked_docs) + batch_size - 1) // batch_size
        for batch_num in range(total_batches):
            start = batch_num * batch_size
            end = min(start + batch_size, len(chunked_docs))

            batch_docs = chunked_docs[start:end]
            batch_ids = chunked_ids[start:end]
            batch_meta = chunked_meta[start:end]

            embeddings = self.embeddings.embed_documents(batch_docs)
            collection.add(
                ids=batch_ids,
                documents=batch_docs,
                embeddings=embeddings,
                metadatas=batch_meta,
            )
            print(f"   ⏳ {pdf_name}: батч {batch_num+1}/{total_batches}")

    def index_all(self, collection_name: str = "fstek_npa"):
        """Индексация всех PDF из NPA_PDF_DIR"""
        npa_dir = os.getenv("NPA_PDF_DIR")
        if not npa_dir:
            raise ValueError("NPA_PDF_DIR не задан в .env")

        pdf_dir = Path(npa_dir)
        pdf_files = list(pdf_dir.glob("*.pdf"))

        if not pdf_files:
            raise FileNotFoundError(f"Нет PDF-файлов в {npa_dir}")

        print(f"📂 Найдено {len(pdf_files)} PDF-файлов")

        collection = self.create_collection(collection_name)
        total_paragraphs = 0

        for pdf_path in pdf_files:
            print(f"\n📄 Обработка: {pdf_path.name}")
            paragraphs = self.load_pdf(str(pdf_path))

            if not paragraphs:
                print(f"   ⚠️  Не найдено структурированных параграфов")
                continue

            ids = [p["id"] for p in paragraphs]
            documents = [p["text"] for p in paragraphs]
            metadatas = [
                {"source": p["source"], "paragraph_id": p["paragraph_id"]}
                for p in paragraphs
            ]

            print(f"   🧮 Индексация {len(documents)} параграфов...")
            self._add_documents_safe(collection, ids, documents, metadatas, pdf_path.name)

            total_paragraphs += len(paragraphs)
            print(f"   ✅ Загружено {len(paragraphs)} параграфов")

        print(f"\n🎉 Всего загружено {total_paragraphs} параграфов из {len(pdf_files)} документов")
        return collection

    def search(self, query: str, n_results: int = 10, collection_name: str = "fstek_npa"):
        """Поиск релевантных требований"""
        collection = self.chroma_client.get_collection(collection_name)
        query_embedding = self.embeddings.embed_query(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )

        return results


if __name__ == "__main__":
    loader = NPALoader()

    # Индексация всех PDF
    collection = loader.index_all()

    # Тестовый поиск
    print("\n" + "=" * 60)
    print("🔍 ТЕСТОВЫЙ ПОИСК")
    print("=" * 60)

    results = loader.search("Требования к антивирусной защите для ГИС 1 класса")

    for i, (doc, meta) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
    )):
        print(f"\n--- Результат {i+1} ---")
        print(f"Источник: {meta.get('source', 'неизвестно')}")
        print(f"Пункт: {meta.get('paragraph_id', 'неизвестно')}")
        print(f"Текст: {doc[:300]}...")
