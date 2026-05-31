#!/bin/bash
# Скрипт запуска системы аттестации ФСТЭК
# Использование: bash fstek-start.sh [start|ui|stop|status|restart]

set -e
PROJECT_DIR="$HOME/projects/fstek-attestation"
VENV_DIR="$PROJECT_DIR/.venv"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_docker() {
    if docker ps > /dev/null 2>&1; then log_ok "Docker работает"; return 0
    else log_warn "Docker не доступен"; return 1; fi
}

check_postgres() {
    if sudo -u postgres pg_isready -q 2>/dev/null; then log_ok "PostgreSQL работает"; return 0
    else
        log_warn "PostgreSQL не запущен, запускаю..."
        sudo pg_ctlcluster 16 main start 2>/dev/null || sudo service postgresql start 2>/dev/null || true
        sleep 3
        if sudo -u postgres pg_isready -q 2>/dev/null; then log_ok "PostgreSQL запущен"; return 0
        else log_error "Не удалось запустить PostgreSQL"; return 1; fi
    fi
}

check_ollama() {
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then log_ok "Ollama работает"; return 0
    else
        log_warn "Ollama не запущен, запускаю..."
        ollama serve > /dev/null 2>&1 & sleep 5
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then log_ok "Ollama запущен"; return 0
        else log_error "Не удалось запустить Ollama"; return 1; fi
    fi
}

start_containers() {
    log_info "Запуск Docker-контейнеров..."
    cd "$PROJECT_DIR"; docker compose up -d 2>/dev/null || true; sleep 5
    log_ok "Контейнеры запущены"
}

start_streamlit() {
    log_info "Запуск Streamlit UI..."
    cd "$PROJECT_DIR"; source "$VENV_DIR/bin/activate"
    if pgrep -f "streamlit run" > /dev/null; then log_warn "Streamlit уже запущен"; return 0; fi
    nohup streamlit run streamlit_app.py --server.port 8501 > /tmp/streamlit_fstek.log 2>&1 &
    sleep 5
    if pgrep -f "streamlit run" > /dev/null; then log_ok "Streamlit запущен: http://localhost:8501"
    else log_error "Streamlit не запустился"; fi
}

stop_all() {
    log_info "Остановка сервисов..."
    pkill -f "streamlit run" 2>/dev/null && log_ok "Streamlit остановлен" || true
    cd "$PROJECT_DIR"; docker compose down 2>/dev/null || true
    pkill -f "ollama serve" 2>/dev/null && log_ok "Ollama остановлен" || true
}

show_status() {
    echo ""; echo "============================================"; echo "   СТАТУС СИСТЕМЫ"; echo "============================================"
    docker ps > /dev/null 2>&1 && echo -e "${GREEN}✅${NC} Docker" || echo -e "${RED}❌${NC} Docker"
    sudo -u postgres pg_isready -q 2>/dev/null && echo -e "${GREEN}✅${NC} PostgreSQL" || echo -e "${RED}❌${NC} PostgreSQL"
    curl -s http://localhost:8001/api/v2/heartbeat > /dev/null 2>&1 && echo -e "${GREEN}✅${NC} ChromaDB" || echo -e "${RED}❌${NC} ChromaDB"
    curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && echo -e "${GREEN}✅${NC} Ollama" || echo -e "${RED}❌${NC} Ollama"
    pgrep -f "streamlit run" > /dev/null && echo -e "${GREEN}✅${NC} Streamlit (8501)" || echo -e "${YELLOW}⚠️${NC}  Streamlit"
    echo "============================================"
}

case "${1:-start}" in
    start|full) check_docker; check_postgres; start_containers; check_ollama; log_info "Все сервисы запущены!";;
    ui) check_docker; check_postgres; start_containers; check_ollama; start_streamlit;;
    stop) stop_all;;
    status) show_status;;
    restart) stop_all; sleep 3; bash "$0" start;;
    *) echo "Команды: start | ui | stop | status | restart";;
esac
