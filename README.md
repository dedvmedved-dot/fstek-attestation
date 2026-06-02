
# Система автоматизированной подготовки к аттестации ФСТЭК

Программный комплекс на базе искусственного интеллекта для автоматизации полного цикла подготовки программно-аппаратных комплексов (ПАК) к аттестации по требованиям ФСТЭК России.

Версия: **2.0.0**

---

## Возможности

### Аудит конфигурации ПАК

- **Покомпонентный аудит** — проверка каждого требования на каждом компоненте (до 624 проверок)
- **Системный аудит** — анализ ПАК как единого комплекса с учётом ролей, компенсации и эшелонирования защиты
- **Пакетный аудит** — анализ одной конфигурации на соответствие нескольким классификациям одновременно

### RAG-чат с экспертом ФСТЭК

- Интерактивное общение с AI-экспертом с автоматическим поиском по базе НПА
- Поддержка 4 провайдеров LLM: DeepSeek, ChatGPT (OpenAI), Perplexity, локальные модели
- Постраничный просмотр 19 нормативных документов
- Сохранение и восстановление истории диалогов
- Загрузка файлов для анализа (PDF, DOCX, XLSX, Markdown)

### Экспорт результатов

- **5 документов:** матрица требований, ведомость несоответствий, целевая конфигурация, программа испытаний, заключение
- **6 форматов:** JSON, DOCX, XLSX, Markdown, PDF, SVG + ZIP-пакет

---

## Требования

| Компонент | Минимально | Рекомендуется |
|-----------|-----------|---------------|
| ОС | Windows 11 + WSL2 Ubuntu 24.04 | — |
| RAM | 32 GB | 128 GB |
| GPU | Не требуется (API) | NVIDIA RTX 5080 (16 GB VRAM) |
| SSD | 500 GB | 2 TB NVMe |
| Docker | Docker Desktop | — |
| Python | 3.11+ | 3.11 (pyenv) |

---

## Быстрый старт

### 1. Клонирование

```bash
git clone https://github.com/dedvmedved-dot/fstek-attestation.git
cd fstek-attestation
```

### 2. Настройка окружения

```bash
python3 -m venv --copies .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Настройка API-ключей

Создайте файл `.env`:

```bash
DEEPSEEK_API_KEY=sk-your-key-here
OPENAI_API_KEY=sk-your-key-here      # опционально
PERPLEXITY_API_KEY=pplx-your-key-here # опционально
NPA_PDF_DIR=/home/ase/fstek-data/npa-pdf
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=fstek_attestation
POSTGRES_USER=fstek_admin
POSTGRES_PASSWORD=your-password
```

### 4. Запуск инфраструктуры

```bash
# Установка Docker-контейнеров
docker compose up -d

# Запуск PostgreSQL (если не в Docker)
sudo pg_ctlcluster 16 main start

# Запуск Ollama (для эмбеддингов)
ollama serve &
ollama pull nomic-embed-text
```

### 5. Индексация нормативных документов

```bash
# Поместите PDF-файлы НПА в ~/fstek-data/npa-pdf/
python npa_loader.py
```

### 6. Запуск веб-интерфейса

```bash
streamlit run streamlit_app.py --server.port 8501
```

Откройте http://localhost:8501

---

## Структура проекта

```
fstek-attestation/
├── audit_graph.py              # Граф покомпонентного аудита (LangGraph)
├── batch_audit.py              # Пакетный аудит (N классификаций)
├── classification_schema.py    # Профиль многофакторной классификации
├── check_env.py                # Проверка окружения
├── db_schema.py                # SQLAlchemy модели (PostgreSQL)
├── docker-compose.yml          # ChromaDB + Redis
├── init.sql                    # Инициализация PostgreSQL
├── input_data.json             # Пример конфигурации ПАК
├── classifications.json        # Пример списка классификаций
├── llm_adapter.py              # Адаптер LLM (DeepSeek / OpenAI / Local)
├── npa_loader.py               # Загрузчик НПА в ChromaDB
├── rag_chat.py                 # RAG-чат с мультипровайдерной поддержкой
├── report_docx.py              # Генератор DOCX
├── report_markdown.py          # Генератор Markdown и PDF
├── report_xlsx.py              # Генератор XLSX
├── system_audit.py             # Системный аудит ПАК
├── target_config_graph.py      # Генератор SVG-схем
├── streamlit_app.py            # Основной веб-интерфейс
├── streamlit_archive.py        # Модуль архива и отчётов
├── streamlit_chat.py           # Модуль RAG-чата
├── requirements.txt            # Python-зависимости
├── prompts/                    # Системные промпты
├── reports/                    # Сгенерированные документы
├── chats/                      # Сохранённые диалоги
└── fstek-start.sh              # Скрипт автозапуска
```

---

## Основные команды

### Управление сервисами

```bash
bash ~/fstek-start.sh status   # Проверка статуса
bash ~/fstek-start.sh start    # Запуск всех сервисов
bash ~/fstek-start.sh ui       # Запуск сервисов + Streamlit
bash ~/fstek-start.sh stop     # Остановка
```

### Аудит

```bash
# Системный аудит
python system_audit.py input_data.json

# Пакетный аудит (несколько классификаций)
python batch_audit.py input_data.json classifications.json
```

---

## База нормативных документов

Система использует 19 нормативно-правовых актов (10 059 структурированных чанков):

| Документ | Тип |
|----------|-----|
| MD2026 | Методический документ ФСТЭК (2026) |
| FSTEK21 | Приказ ФСТЭК №21 |
| FSTEK239 | Приказ ФСТЭК №239 |
| FSTEK117 | Приказ ФСТЭК №117 |
| FSTEK77 | Приказ ФСТЭК №77 |
| FSTEK187 | Приказ ФСТЭК №187 |
| FZ152 | Федеральный закон №152 |
| FZ187 | Федеральный закон №187 |
| P1119 | Постановление №1119 |
| GOST_R_59547-2021 | ГОСТ Р 59547 |
| GOST_R_59548-2022 | ГОСТ Р 59548 |
| ... | и другие |

---

## Лицензия

Проект находится в стадии активной разработки. Использование в коммерческих целях — по согласованию с автором.

---

## Контакты

GitHub: [dedvmedved-dot](https://github.com/dedvmedved-dot)

---

## Changelog

### v2.0.0 (июнь 2026)

- Добавлен пакетный аудит (batch_audit.py)
- Добавлен RAG-чат с мультипровайдерной поддержкой
- Добавлено сохранение и восстановление истории чатов
- Добавлен постраничный просмотр 19 НПА
- Добавлен экспорт в Markdown и PDF
- Добавлен генератор SVG-схем целевой конфигурации
- Полная переиндексация НПА (10 059 структурированных чанков)
- Обновлён интерфейс (5 вкладок)

### v1.0.0 (май 2026)

- Первая версия
- Покомпонентный и системный аудит
- Экспорт в JSON, DOCX, XLSX
- RAG-поиск по 19 НПА
- Streamlit UI
