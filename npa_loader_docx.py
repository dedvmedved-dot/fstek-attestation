"""
Загрузчик НПА из DOCX с точным сохранением структуры.
Каждый пункт документа становится отдельным чанком с полным путём.
"""

import re
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
load_dotenv()

from docx import Document
from chromadb import HttpClient
from chromadb.config import Settings
from llm_adapter import LLMFactory


class NPALoaderDOCX:
    """Загрузчик DOCX с иерархическим чанкингом"""
    
    def __init__(self, docx_dir: str = None):
        import os
        self.docx_dir = Path(docx_dir or os.getenv("NPA_DOCX_DIR", 
                            os.path.expanduser("~/fstek-data/npa-docx")))
        
        self.chroma_client = HttpClient(
            host="localhost", port=8001,
            settings=Settings(anonymized_telemetry=False),
        )
        self.embeddings = LLMFactory.get_embeddings()
    
    def extract_structure(self, docx_path: str) -> List[Dict]:
        """
        Извлекает структурированное содержимое DOCX.
        Каждый параграф получает:
        - paragraph_id: точный номер пункта (1.1, 2.3.1) или заголовок
        - parent_path: полный путь (I. Общие положения > 1.2 > 1.2.3)
        - level: уровень вложенности (0=заголовок раздела, 1=пункт, 2=подпункт)
        """
        doc = Document(docx_path)
        doc_name = Path(docx_path).stem
        
        paragraphs = []
        heading_stack = []  # Стек заголовков для построения пути
        current_number = None
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text or len(text) < 10:
                continue
            
            style_name = para.style.name if para.style else ""
            
            # Определяем уровень по стилю
            if style_name.startswith("Heading") or style_name.startswith("heading"):
                try:
                    level = int(style_name.split()[-1])
                except:
                    level = 1
                
                # Очищаем номер от текста заголовка
                number_match = re.match(r'^((?:[IVX]+\.|\d+\.?)+)\s', text)
                if number_match:
                    number = number_match.group(1).strip()
                else:
                    number = text[:50]
                
                # Обновляем стек
                while len(heading_stack) >= level:
                    heading_stack.pop()
                heading_stack.append(number)
                
                parent_path = " > ".join(heading_stack)
                
                paragraphs.append({
                    "id": f"{doc_name}::heading::{number}",
                    "paragraph_id": number,
                    "text": text[:2000],
                    "source": doc_name,
                    "parent_path": parent_path,
                    "level": level,
                    "is_heading": True,
                })
                current_number = number
            
            elif style_name.startswith("List") or style_name.startswith("list"):
                # Элемент списка — привязываем к текущему заголовку
                if current_number:
                    parent_path = " > ".join(heading_stack)
                else:
                    parent_path = doc_name
                
                list_id = f"{current_number or 'item'}_{len(paragraphs)}"
                
                paragraphs.append({
                    "id": f"{doc_name}::list::{list_id}",
                    "paragraph_id": current_number or "list",
                    "text": text[:2000],
                    "source": doc_name,
                    "parent_path": parent_path,
                    "level": len(heading_stack),
                    "is_heading": False,
                })
            
            elif style_name.startswith("Normal") or style_name.startswith("normal") or not style_name:
                # Обычный текст — ищем номер пункта в начале
                number_match = re.match(r'^(\d+(?:\.\d+)*)\s', text)
                if number_match:
                    number = number_match.group(1)
                    # Определяем уровень по количеству точек
                    level = number.count('.') + 1
                    
                    while len(heading_stack) >= level:
                        heading_stack.pop()
                    heading_stack.append(number)
                    parent_path = " > ".join(heading_stack)
                    current_number = number
                else:
                    parent_path = " > ".join(heading_stack) if heading_stack else doc_name
                
                paragraphs.append({
                    "id": f"{doc_name}::text::{current_number or len(paragraphs)}",
                    "paragraph_id": current_number or f"text_{len(paragraphs)}",
                    "text": text[:2000],
                    "source": doc_name,
                    "parent_path": parent_path,
                    "level": len(heading_stack),
                    "is_heading": bool(number_match),
                })
        
        return paragraphs
    
    def index_all(self, collection_name: str = "fstek_npa"):
        """Индексация всех DOCX из папки"""
        docx_files = list(self.docx_dir.glob("*.docx"))
        
        if not docx_files:
            print(f"❌ Нет DOCX-файлов в {self.docx_dir}")
            return
        
        print(f"📂 Найдено {len(docx_files)} DOCX-файлов")
        
        # Создаём новую коллекцию
        try:
            self.chroma_client.delete_collection(collection_name)
            print(f"🗑️ Старая коллекция удалена")
        except:
            pass
        
        collection = self.chroma_client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        
        total_chunks = 0
        for docx_path in docx_files:
            print(f"\n📄 {docx_path.name}")
            paragraphs = self.extract_structure(str(docx_path))
            
            if not paragraphs:
                print("   ⚠️ Нет структурированного текста")
                continue
            
            # Статистика по уровням
            headings = sum(1 for p in paragraphs if p["is_heading"])
            print(f"   Параграфов: {len(paragraphs)} (заголовков: {headings})")
            
            # Показываем примеры заголовков
            for p in paragraphs[:5]:
                if p["is_heading"]:
                    print(f"     📌 {p['paragraph_id']} [путь: {p['parent_path']}]")
            
            # Индексация
            ids = [p["id"] for p in paragraphs]
            docs = [p["text"][:2000] for p in paragraphs]
            metas = [{
                "source": p["source"],
                "paragraph_id": p["paragraph_id"],
                "parent_path": p["parent_path"],
                "level": p["level"],
                "is_heading": p["is_heading"],
            } for p in paragraphs]
            
            for i in range(0, len(docs), 30):
                batch = slice(i, i+30)
                embs = self.embeddings.embed_documents(docs[batch])
                collection.add(ids=ids[batch], documents=docs[batch], 
                             embeddings=embs, metadatas=metas[batch])
                print(f"   Батч {i//30 + 1}/{(len(docs)-1)//30 + 1}")
            
            total_chunks += len(paragraphs)
        
        print(f"\n✅ Всего загружено {total_chunks} чанков из {len(docx_files)} документов")
        
        # Тестовый поиск
        print("\n🔍 Тестовый поиск...")
        test_docs = self.search("антивирусная защита", collection_name)
        for i, doc in enumerate(test_docs[:3], 1):
            print(f"   {i}. {doc['source']} [{doc['paragraph_id']}] — {doc['text'][:100]}...")
    
    def search(self, query: str, collection_name: str = "fstek_npa", n_results: int = 10) -> List[Dict]:
        """Поиск с учётом структуры"""
        collection = self.chroma_client.get_collection(collection_name)
        qe = self.embeddings.embed_query(query)
        results = collection.query(query_embeddings=[qe], n_results=n_results)
        
        docs = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            docs.append({
                "text": doc,
                "source": meta.get("source", ""),
                "paragraph_id": meta.get("paragraph_id", ""),
                "parent_path": meta.get("parent_path", ""),
                "level": meta.get("level", 0),
                "is_heading": meta.get("is_heading", False),
            })
        return docs


if __name__ == "__main__":
    loader = NPALoaderDOCX()
    loader.index_all()
