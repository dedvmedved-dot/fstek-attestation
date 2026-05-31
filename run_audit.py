"""
Универсальный запуск аудита из JSON-файла.
Не требует изменения кода при смене структуры входных данных.
"""

import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from audit_graph import build_audit_graph, AuditState
from db_schema import init_db


def load_input_data(json_path: str) -> dict:
    """Загрузка и валидация входных данных"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Автоматическое извлечение полей
    classification = data.get("classification", {})
    components = data.get("components", [])
    
    # Нормализация компонентов под формат AuditState
    normalized_components = []
    for comp in components:
        normalized_components.append({
            "component_name": comp.get("component_name", comp.get("name", "Неизвестный компонент")),
            "component_type": comp.get("component_type", comp.get("type", "не указан")),
            "current_configuration": comp.get("configuration", comp.get("config", {})),
        })
    
    return {
        "system_name": data.get("system_name", "Без названия"),
        "components": normalized_components,
        "classification": classification,
        "raw_data": data,  # Сохраняем оригинал для отчёта
    }


def build_initial_state(input_data: dict) -> AuditState:
    """Построение начального состояния аудита"""
    classification = input_data["classification"]
    
    # Собираем все классификационные признаки в одну строку
    class_parts = []
    if classification.get("fstek_117_class"):
        class_parts.append(classification["fstek_117_class"])
    if classification.get("fstek_21_class"):
        class_parts.append(classification["fstek_21_class"])
    if classification.get("pp1119_level"):
        class_parts.append(classification["pp1119_level"])
    if classification.get("threat_type"):
        class_parts.append(classification["threat_type"])
    if classification.get("has_dsp"):
        class_parts.append("ДСП")
    
    classification_level = " / ".join(class_parts) if class_parts else "Не указан"
    
    return {
        "system_name": input_data["system_name"],
        "system_type": classification.get("system_type", ""),
        "organization_type": classification.get("organization_type", ""),
        "fstek_117_class": classification.get("fstek_117_class", ""),
        "fstek_21_class": classification.get("fstek_21_class", ""),
        "has_dsp": classification.get("has_dsp", False),
        "ispdn_category": classification.get("ispdn_category", ""),
        "ispdn_subjects_count": classification.get("ispdn_subjects_count", 0),
        "threat_type": classification.get("threat_type", ""),
        "pp1119_level": classification.get("pp1119_level", ""),
        "classification_level": classification_level,
        "components": input_data["components"],
        "requirements": [],
        "current_requirement_idx": 0,
        "current_component_idx": 0,
        "audit_results": [],
        "status": "init",
        "error_message": "",
    }


def main():
    # Путь к JSON-файлу (аргумент командной строки или по умолчанию)
    json_path = sys.argv[1] if len(sys.argv) > 1 else "input_data.json"
    
    if not Path(json_path).exists():
        print(f"❌ Файл {json_path} не найден")
        print(f"Использование: python run_audit.py [путь_к_json]")
        sys.exit(1)
    
    print(f"📂 Загрузка данных: {json_path}")
    input_data = load_input_data(json_path)
    
    print(f"🖥️  Система: {input_data['system_name']}")
    print(f"📋 Компонентов: {len(input_data['components'])}")
    print(f"🔒 Классификация: {input_data['classification']}")
    
    # Инициализация БД
    init_db()
    
    # Построение начального состояния
    initial_state = build_initial_state(input_data)
    
    # Запуск аудита
    print("\n" + "=" * 60)
    print("🚀 ЗАПУСК АУДИТА ФСТЭК")
    print("=" * 60)
    
    graph = build_audit_graph()
    config = {"configurable": {"thread_id": f"audit-{input_data['system_name']}"}}
    final_state = graph.invoke(initial_state, config)
    
    # Сохранение результатов
    results = final_state["audit_results"]
    compliant = sum(1 for r in results if r.get("compliance_status") == "COMPLIANT")
    non_compliant = sum(1 for r in results if r.get("compliance_status") == "NON_COMPLIANT")
    
    print("\n" + "=" * 60)
    print("✅ АУДИТ ЗАВЕРШЁН")
    print("=" * 60)
    print(f"Соответствует: {compliant}")
    print(f"Не соответствует: {non_compliant}")
    print(f"Требует уточнения: {sum(1 for r in results if r.get('compliance_status') == 'NEED_MORE_INFO')}")
    
    # Итоговый отчёт
    report_dir = Path("reports")
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"audit_{input_data['system_name']}_{input_data['classification'].get('fstek_117_class', '')}_{input_data['classification'].get('pp1119_level', '')}.json"
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "system": input_data["raw_data"],
            "audit_summary": {
                "total_requirements": len(results),
                "compliant": compliant,
                "non_compliant": non_compliant,
                "need_more_info": sum(1 for r in results if r.get("compliance_status") == "NEED_MORE_INFO"),
            },
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 Полный отчёт: {report_path}")
    # Генерация DOCX
    try:
        from report_docx import FSTEKReportGenerator
        docx_gen = FSTEKReportGenerator(str(report_path))
        docx_path = docx_gen.generate()
        print(f"📄 Протокол DOCX: {docx_path}")
    except ImportError:
        print("⚠️  python-docx не установлен. Установите: pip install python-docx")
    except Exception as e:
        print(f"⚠️  Ошибка генерации DOCX: {e}")
    
    # Генерация XLSX
    try:
        from report_xlsx import FSTEKExcelGenerator
        xlsx_gen = FSTEKExcelGenerator(str(report_path))
        xlsx_path = xlsx_gen.generate()
        print(f"📊 Матрица Excel: {xlsx_path}")
    except ImportError:
        print("⚠️  openpyxl не установлен. Установите: pip install openpyxl")
    except Exception as e:
        print(f"⚠️  Ошибка генерации XLSX: {e}")
    
    # Генерация DOCX
    try:
        from report_docx import FSTEKReportGenerator
        docx_gen = FSTEKReportGenerator(str(report_path))
        docx_path = docx_gen.generate()
        print(f"📄 Протокол DOCX: {docx_path}")
    except ImportError:
        print("⚠️  python-docx не установлен. Установите: pip install python-docx")
    except Exception as e:
        print(f"⚠️  Ошибка генерации DOCX: {e}")
    
    # Генерация XLSX
    try:
        from report_xlsx import FSTEKExcelGenerator
        xlsx_gen = FSTEKExcelGenerator(str(report_path))
        xlsx_path = xlsx_gen.generate()
        print(f"📊 Матрица Excel: {xlsx_path}")
    except ImportError:
        print("⚠️  openpyxl не установлен. Установите: pip install openpyxl")
    except Exception as e:
        print(f"⚠️  Ошибка генерации XLSX: {e}")

if __name__ == "__main__":
    main()
