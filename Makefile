.PHONY: help env check infra load-npa dev-audit local-audit ui clean stop

help:
	@echo "Система аттестации ФСТЭК"
	@echo ""
	@echo "Команды:"
	@echo "  make check-env    - Проверка окружения"
	@echo "  make infra        - Запуск PostgreSQL, ChromaDB, Redis"
	@echo "  make load-npa     - Индексация PDF НПА в ChromaDB"
	@echo "  make dev-audit    - Аудит через DeepSeek API"
	@echo "  make local-audit  - Аудит через локальный llama.cpp"
	@echo "  make ui           - Запуск Streamlit интерфейса"
	@echo "  make stop         - Остановка всех контейнеров"
	@echo "  make clean        - Полная очистка данных"

check-env:
	python check_env.py

infra:
	docker compose up -d
	@echo "⏳ Ожидание PostgreSQL..."
	@sleep 5
	docker compose ps

load-npa:
	python npa_loader.py

dev-audit:
	@echo "🔧 Запуск аудита с DeepSeek API..."
	LLM_PROVIDER=deepseek python audit_graph.py

local-audit:
	@echo "🔧 Запуск аудита с локальной моделью..."
	@echo "⚠️  Убедитесь, что llama-server запущен на порту 8080"
	LLM_PROVIDER=local python audit_graph.py

ui:
	streamlit run streamlit_app.py --server.port 8501

stop:
	docker compose down

clean:
	docker compose down -v
	rm -rf data/
	@echo "✅ Все данные удалены"
