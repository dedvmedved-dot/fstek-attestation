# Развёртывание системы аттестации ФСТЭК

## 1. Клонирование
git clone https://github.com/dedvmedved-dot/fstek-attestation.git
cd fstek-attestation

## 2. Окружение
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo apt install graphviz -y
cp .env.example .env
# Отредактируйте .env

## 3. Инфраструктура
docker compose up -d
sudo apt install postgresql -y
sudo pg_ctlcluster 16 main start
python db_schema.py

## 4. НПА
mkdir -p ~/fstek-data/npa-pdf
# Положите PDF в папку
python npa_loader.py

## 5. Запуск
bash fstek-start.sh ui



---

## Что ещё нужно скопировать вручную

| Что | Почему не в Git | Как перенести |
|-----|-----------------|---------------|
| **PDF-файлы НПА** (19 шт.) | Большие бинарные файлы, не для Git | Скопировать папку `~/fstek-data/npa-pdf/` |
| **Модель Ollama** (nomic-embed-text) | ~274 MB, не для Git | `ollama pull nomic-embed-text` на новом ПК |
| **DeepSeek API ключ** | Секрет | Скопировать из `.env` |

---

## Полная инструкция для нового компьютера

Добавьте в `SETUP.md`:

```bash
cat >> SETUP.md << 'EOF'

## Дополнительно для полного переноса

### 8. Скопировать НПА

Старого ПК:
```bash
scp -r ~/fstek-data/npa-pdf user@new-pc:~/fstek-data/
```

Или через флешку скопировать папку `fstek-data/npa-pdf/`.

### 9. Загрузить модель эмбеддингов

```bash
ollama pull nomic-embed-text
```

### 10. Загрузить локальную LLM (опционально)

```bash
ollama pull qwen2.5:32b-instruct-q4_K_M
```
EOF
```

---

## Итог: что в Git, что вручную

| Способ | Файлы |
|--------|-------|
| **Git** | Код, конфиги, примеры, инструкции |
| **Копировать вручную** | PDF НПА (~10 MB) |
| **Скачать на месте** | Модели Ollama, Docker-образы |
| **Ввести** | DeepSeek API ключ |

С этим набором система разворачивается на новом компьютере за 15-20 минут.

