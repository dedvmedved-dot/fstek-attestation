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
