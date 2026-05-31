"""
LangGraph-граф для аудита ПАК на соответствие требованиям ФСТЭК.
Основной модуль системы.
"""

import os
import json
from typing import TypedDict, List, Annotated
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from classification_schema import ClassificationProfile
load_dotenv()

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage
from chromadb import HttpClient
from chromadb.config import Settings

from llm_adapter import LLMFactory
from db_schema import init_db, get_session, System, SystemComponent, NPARequirement, AuditTrail

# ========== Состояние графа ==========
class AuditState(TypedDict):
    system_name: str
    classification_level: str
    components: List[dict]
    requirements: List[dict]
    current_requirement_idx: int
    current_component_idx: int
    audit_results: Annotated[List[dict], "merge"]
    status: str
    error_message: str

# ========== Системный промт ==========
AUDITOR_SYSTEM_PROMPT = """Ты — ведущий эксперт-аудитор ФСТЭК России и архитектор защищённых программно-аппаратных комплексов.

ТВОЯ ЗАДАЧА:
Строго следовать нормативно-правовым актам РФ, не додумывать требования и оперировать только фактами из предоставленного контекста.

ПОРЯДОК ДЕЙСТВИЙ:
1. Изучи "Выдержку из НПА" — конкретное требование.
2. Проанализируй текущие "Параметры ПАК и ПО".
3. Дай оценку: СООТВЕТСТВУЕТ или НЕ СООТВЕТСТВУЕТ.
4. Если НЕ СООТВЕТСТВУЕТ — сформулируй замечание и предложи изменение конфигурации.
5. Если СООТВЕТСТВУЕТ — подтверди со ссылкой на параметры.
6. Если информации недостаточно — укажи "NEED_MORE_INFO".

ФОРМАТ ОТВЕТА: Только JSON, без пояснений."""

# ========== ChromaDB клиент ==========
def get_chroma_collection():
    client = HttpClient(
        host=os.getenv("CHROMA_HOST", "localhost"),
        port=int(os.getenv("CHROMA_PORT", "8001")),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_collection("fstek_npa")


# ========== Узел 1: Извлечение требований ==========
# ========== Узел 1: Извлечение требований ==========
def extract_requirements(state: AuditState) -> AuditState:
    print(f"\n{'='*60}")
    print(f"📋 ЭТАП 1: Извлечение требований")
    print(f"{'='*60}")
    
    # Создаём профиль классификации
    profile = ClassificationProfile(
        system_type=state.get("system_type", "ГИС"),
        organization_type=state.get("organization_type", ""),
        fstek_117_class=state.get("fstek_117_class", ""),
        has_dsp=state.get("has_dsp", False),
        ispdn_category=state.get("ispdn_category", ""),
        ispdn_subjects_count=state.get("ispdn_subjects_count", 0),
        threat_type=state.get("threat_type", ""),
        pp1119_level=state.get("pp1119_level", ""),
    )
    
    print(profile.get_description())
    
    from llm_adapter import LLMFactory
    collection = get_chroma_collection()
    emb = LLMFactory.get_embeddings()
    
    search_queries = profile.get_search_queries()
    all_requirements = {}
    
    for query in search_queries:
        print(f"🔍 Поиск: {query[:80]}...")
        try:
            qe = emb.embed_query(query)
            results = collection.query(query_embeddings=[qe], n_results=5)
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                req_id = meta.get("paragraph_id", "unknown")
                if req_id not in all_requirements:
                    all_requirements[req_id] = {
                        "paragraph_id": req_id,
                        "source_document": meta.get("source", "unknown"),
                        "text": doc,
                    }
        except Exception as e:
            print(f"⚠️  Ошибка: {e}")
    
    requirements = list(all_requirements.values())
    print(f"✅ Найдено {len(requirements)} уникальных требований")
    
    state["requirements"] = requirements
    state["current_requirement_idx"] = 0
    state["current_component_idx"] = 0
    state["audit_results"] = []
    state["status"] = "in_progress"
    return state
# ========== Узел 2: Аудит одного требования ==========
def audit_step(state: AuditState) -> AuditState:
    req_idx = state["current_requirement_idx"]
    comp_idx = state["current_component_idx"]

    if req_idx >= len(state["requirements"]):
        state["status"] = "completed"
        return state

    requirement = state["requirements"][req_idx]
    component = state["components"][comp_idx]

    print(f"\n--- Аудит {req_idx+1}/{len(state['requirements'])} → {comp_idx+1}/{len(state['components'])} ---")
    print(f"Требование: {requirement['paragraph_id']} | Компонент: {component['component_name']}")

    llm = LLMFactory.get_llm(mode="audit", temperature=0.1)

    user_prompt = f"""
### ИСХОДНЫЕ ДАННЫЕ

**Уровень классификации:** {state['classification_level']}

**Выдержка из НПА:**
Источник: {requirement['source_document']}
Пункт: {requirement['paragraph_id']}
Текст: {requirement['text'][:2000]}

**Параметры компонента:**
Название: {component['component_name']}
Тип: {component.get('component_type', 'не указан')}
Конфигурация: {json.dumps(component.get('current_configuration', {}), ensure_ascii=False, indent=2)}

### ЗАДАНИЕ
Проведи анализ соответствия и верни строго JSON:

{{
  "compliance_status": "COMPLIANT" | "NON_COMPLIANT" | "NEED_MORE_INFO",
  "analysis": {{
    "current_state": "Что есть сейчас",
    "gap": "Чего не хватает или подтверждение",
    "risk_level": "HIGH" | "MEDIUM" | "LOW"
  }},
  "developer_note": "Замечание для протокола",
  "recommended_configuration_change": {{
    "action": "ENABLE" | "DISABLE" | "INSTALL" | "CONFIGURE",
    "target": "Модуль/подсистема",
    "new_value": "Конкретное изменение",
    "justification": "Обоснование"
  }}
}}
"""
    try:
        response = llm.invoke([
            SystemMessage(content=AUDITOR_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content)
        result["requirement_id"] = requirement["paragraph_id"]
        result["source_document"] = requirement["source_document"]
        result["component_name"] = component["component_name"]
        state["audit_results"].append(result)
        print(f"   Результат: {result.get('compliance_status', 'UNKNOWN')}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        state["audit_results"].append({
            "requirement_id": requirement["paragraph_id"],
            "component_name": component["component_name"],
            "compliance_status": "ERROR",
            "error": str(e),
        })

    if comp_idx + 1 < len(state["components"]):
        state["current_component_idx"] = comp_idx + 1
    else:
        state["current_component_idx"] = 0
        state["current_requirement_idx"] = req_idx + 1

    return state

# ========== Узел 3: Отчёт ==========
def generate_report(state: AuditState) -> AuditState:
    print(f"\n{'='*60}")
    print(f"📊 ЭТАП 3: Генерация отчёта")
    print(f"{'='*60}")

    results = state["audit_results"]
    compliant = sum(1 for r in results if r.get("compliance_status") == "COMPLIANT")
    non_compliant = sum(1 for r in results if r.get("compliance_status") == "NON_COMPLIANT")
    need_info = sum(1 for r in results if r.get("compliance_status") == "NEED_MORE_INFO")
    errors = sum(1 for r in results if r.get("compliance_status") == "ERROR")

    print(f"✅ Соответствует: {compliant}")
    print(f"❌ Не соответствует: {non_compliant}")
    print(f"❓ Требует уточнения: {need_info}")
    print(f"⚠️  Ошибок: {errors}")

    # Сохранение JSON
    report_path = Path("reports") / f"audit_{state['system_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "system_name": state["system_name"],
            "classification_level": state["classification_level"],
            "total": len(results),
            "compliant": compliant,
            "non_compliant": non_compliant,
            "need_more_info": need_info,
            "errors": errors,
            "details": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"📄 Отчёт сохранён: {report_path}")
    return state


def should_continue_audit(state: AuditState) -> str:
    if state["status"] == "completed":
        return "generate_report"
    return "audit_step"


def build_audit_graph():
    workflow = StateGraph(AuditState)
    workflow.add_node("extract_requirements", extract_requirements)
    workflow.add_node("audit_step", audit_step)
    workflow.add_node("generate_report", generate_report)
    workflow.set_entry_point("extract_requirements")
    workflow.add_edge("extract_requirements", "audit_step")
    workflow.add_conditional_edges("audit_step", should_continue_audit, {
        "audit_step": "audit_step",
        "generate_report": "generate_report",
    })
    workflow.add_edge("generate_report", END)
    return workflow.compile(checkpointer=MemorySaver())


# ========== Демо-запуск ==========
def run_demo_audit():
    init_db()
    initial_state: AuditState = {
        "system_name": "ГИС ГУП Пример",
        "system_type": "ГИС государственного унитарного предприятия",
        "organization_type": "государственное унитарное предприятие",
        "fstek_117_class": "К2",
        "has_dsp": True,
        "ispdn_category": "иные категории ПДн",
        "ispdn_subjects_count": 50000,
        "threat_type": "3-й тип",
        "pp1119_level": "УЗ-4",
        "classification_level": "К2 / УЗ-4 / 3-й тип угроз / ДСП",
        "components": [
            {
                "component_name": "Astra Linux Special Edition 1.7.3",
                "component_type": "ОС",
                "current_configuration": {
                    "selinux": "enforcing",
                    "firewall": "disabled",
                    "auditd": "enabled",
                }
            },
            {
                "component_name": "КриптоПро CSP 5.0",
                "component_type": "СКЗИ",
                "current_configuration": {
                    "version": "5.0.12000",
                    "mode": "базовый",
                }
            },
        ],
        "requirements": [],
        "current_requirement_idx": 0,
        "current_component_idx": 0,
        "audit_results": [],
        "status": "init",
        "error_message": "",
    }

    print("\n" + "=" * 60)
    print("🚀 ЗАПУСК АУДИТА ФСТЭК")
    print("=" * 60)

    graph = build_audit_graph()
    config = {"configurable": {"thread_id": "demo-audit-1"}}
    final_state = graph.invoke(initial_state, config)

    print("\n" + "=" * 60)
    print("✅ АУДИТ ЗАВЕРШЁН")
    print("=" * 60)
    return final_state


if __name__ == "__main__":
    run_demo_audit()
