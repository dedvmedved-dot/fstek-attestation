"""
Системный аудит ПАК как единого комплекса.
Анализирует весь ПАК целиком на соответствие каждому требованию НПА.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

from llm_adapter import LLMFactory
from chromadb import HttpClient
from chromadb.config import Settings
from classification_schema import ClassificationProfile, filter_requirements
from langchain_core.messages import HumanMessage, SystemMessage


class SystemAuditor:
    """Аудитор ПАК как единой системы"""
    
    def __init__(self):
        self.llm = LLMFactory.get_llm(mode="audit", temperature=0.1)
        self.embeddings = LLMFactory.get_embeddings()
        self.chroma_client = HttpClient(
            host="localhost",
            port=8001,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma_client.get_collection("fstek_npa")
    
    def build_system_description(self, pak_data: dict) -> str:
        """
        Строит целостное описание ПАК как единого комплекса.
        Учитывает взаимосвязи, защиту, компенсацию, дублирование.
        """
        parts = []
        
        # Назначение системы
        parts.append(f"## НАЗНАЧЕНИЕ СИСТЕМЫ")
        parts.append(f"Система: {pak_data.get('system_name', 'ПАК')}")
        parts.append(f"Тип: {pak_data.get('classification', {}).get('system_type', '')}")
        parts.append(f"Класс: {pak_data.get('classification', {}).get('fstek_117_class', '')}")
        parts.append(f"Уровень ПДн: {pak_data.get('classification', {}).get('pp1119_level', '')}")
        parts.append(f"Тип угроз: {pak_data.get('classification', {}).get('threat_type', '')}")
        parts.append(f"ДСП: {'Да' if pak_data.get('classification', {}).get('has_dsp') else 'Нет'}")
        parts.append(f"Субъектов ПДн: {pak_data.get('classification', {}).get('ispdn_subjects_count', 0)}")
        
        # Защищаемая информация
        protected = pak_data.get("protected_info", {})
        if protected:
            parts.append(f"\n## ЗАЩИЩАЕМАЯ ИНФОРМАЦИЯ")
            for cat, desc in protected.items():
                parts.append(f"- {cat}: {desc}")
        
        # Архитектура защиты
        parts.append(f"\n## АРХИТЕКТУРА ЗАЩИТЫ (КАК ЕДИНЫЙ КОМПЛЕКС)")
        parts.append(self._analyze_protection_architecture(pak_data))
        
        # Компоненты с их ролью в защите
        parts.append(f"\n## КОМПОНЕНТЫ И ИХ РОЛЬ В ОБЕСПЕЧЕНИИ ЗАЩИЩЁННОСТИ")
        components = pak_data.get("components", [])
        for comp in components:
            name = comp.get("component_name", comp.get("name", ""))
            comp_type = comp.get("component_type", comp.get("type", ""))
            role = self._determine_role(comp)
            config = comp.get("configuration", comp.get("config", {}))
            
            parts.append(f"\n### {name}")
            parts.append(f"Тип: {comp_type}")
            parts.append(f"Роль в системе защиты: {role}")
            parts.append(f"Конфигурация:")
            for k, v in list(config.items())[:10]:
                parts.append(f"  - {k}: {v}")
        
        # Взаимосвязи и компенсация
        parts.append(f"\n## ВЗАИМОСВЯЗИ КОМПОНЕНТОВ")
        parts.append(self._analyze_interconnections(pak_data))
        
        # Целевые показатели
        kpis = pak_data.get("target_kpis", {})
        if kpis:
            parts.append(f"\n## ЦЕЛЕВЫЕ ПОКАЗАТЕЛИ")
            for k, v in kpis.items():
                parts.append(f"- {k}: {v}")
        
        return "\n".join(parts)
    
    def _determine_role(self, component: dict) -> str:
        """Определяет роль компонента в системе защиты"""
        comp_type = component.get("component_type", component.get("type", "")).lower()
        name = component.get("component_name", component.get("name", "")).lower()
        config = component.get("configuration", component.get("config", {}))
        
        roles = []
        
        # Анализ по типу
        if any(w in comp_type for w in ["ос", "операционная"]):
            roles.append("Фундамент защиты (ОС)")
        if any(w in comp_type for w in ["скзи", "крипто"]):
            roles.append("Криптографическая защита информации")
        if any(w in comp_type for w in ["антивирус", "kaspersky"]):
            roles.append("Антивирусная защита")
        if any(w in comp_type for w in ["ids", "сов", "suricata", "обнаружение"]):
            roles.append("Обнаружение вторжений")
        if any(w in comp_type for w in ["аутентифик", "freeipa", "ldap"]):
            roles.append("Централизованная аутентификация и управление доступом")
        if any(w in comp_type for w in ["кластер", "отказоустой", "pacemaker", "drbd"]):
            roles.append("Обеспечение отказоустойчивости и непрерывности")
        if any(w in comp_type for w in ["сервер", "платформа"]):
            roles.append("Аппаратная платформа")
            if "витязь" in str(config).lower() or "замок" in str(config).lower():
                roles.append("Доверенная загрузка")
        if any(w in comp_type for w in ["коммутатор", "сетевое"]):
            roles.append("Сетевая инфраструктура и сегментирование")
        if any(w in comp_type for w in ["мониторинг", "prometheus", "grafana"]):
            roles.append("Мониторинг и аудит событий")
        if any(w in comp_type for w in ["шифрование", "luks", "dm-crypt"]):
            roles.append("Шифрование данных на носителях")
        if any(w in comp_type for w in ["целостн", "parsec", "aide", "зпс"]):
            roles.append("Контроль целостности")
        if any(w in comp_type for w in ["виртуал", "kvm"]):
            roles.append("Виртуализация и изоляция сред")
        
        if not roles:
            roles.append("Вспомогательный компонент")
        
        return "; ".join(roles)
    
    def _analyze_protection_architecture(self, pak_data: dict) -> str:
        """Анализирует архитектуру защиты как единого комплекса"""
        components = pak_data.get("components", [])
        
        # Группируем по слоям защиты
        layers = {
            "Физический уровень": [],
            "Сетевой уровень": [],
            "Уровень ОС": [],
            "Уровень приложений": [],
            "Уровень данных": [],
            "Уровень мониторинга": [],
        }
        
        for comp in components:
            comp_type = comp.get("component_type", comp.get("type", "")).lower()
            name = comp.get("component_name", comp.get("name", ""))
            
            if any(w in comp_type for w in ["сервер", "платформа", "замок", "витязь"]):
                layers["Физический уровень"].append(name)
            if any(w in comp_type for w in ["коммутатор", "сетевое", "межсетев"]):
                layers["Сетевой уровень"].append(name)
            if any(w in comp_type for w in ["ос", "операционная"]):
                layers["Уровень ОС"].append(name)
            if any(w in comp_type for w in ["вм", "приложение", "кадры", "документооборот"]):
                layers["Уровень приложений"].append(name)
            if any(w in comp_type for w in ["шифрование", "luks", "drbd", "хранилище", "скзи"]):
                layers["Уровень данных"].append(name)
            if any(w in comp_type for w in ["мониторинг", "ids", "антивирус", "аудит"]):
                layers["Уровень мониторинга"].append(name)
        
        description = "Эшелонированная защита ПАК построена по принципу defense-in-depth:\n"
        for layer, items in layers.items():
            if items:
                description += f"\n{layer}: {', '.join(items)}"
        
        return description
    
    def _analyze_interconnections(self, pak_data: dict) -> str:
        """Анализирует взаимосвязи и компенсационные механизмы"""
        components = pak_data.get("components", [])
        
        interconnections = []
        
        # Ищем связи
        has_drbd = any("drbd" in str(c).lower() for c in components)
        has_pacemaker = any("pacemaker" in str(c).lower() for c in components)
        has_luks = any("luks" in str(c).lower() for c in components)
        has_kaspersky = any("kaspersky" in str(c).lower() for c in components)
        has_suricata = any("suricata" in str(c).lower() for c in components)
        has_freeipa = any("freeipa" in str(c).lower() for c in components)
        has_parsec = any("parsec" in str(c).lower() for c in components)
        
        if has_drbd and has_pacemaker:
            interconnections.append("- DRBD + Pacemaker: отказоустойчивое хранение с автоматическим восстановлением (RPO=0, RTO≤60с)")
        if has_luks and has_drbd:
            interconnections.append("- LUKS + DRBD: шифрование данных на всех узлах кластера с синхронной репликацией")
        if has_kaspersky and has_suricata:
            interconnections.append("- Kaspersky ES + Suricata IDS: эшелонированная защита от ВПО (хост + сеть)")
        if has_freeipa and has_parsec:
            interconnections.append("- FreeIPA + PARSEC: централизованное управление доступом с мандатным контролем целостности")
        
        if not interconnections:
            interconnections.append("- Компоненты функционируют независимо. Рекомендуется усилить интеграцию СЗИ.")
        
        return "\n".join(interconnections)
    
    def extract_requirements(self, classification: dict) -> List[dict]:
        """Извлекает применимые требования НПА"""
        profile = ClassificationProfile(
            system_type=classification.get("system_type", ""),
            organization_type=classification.get("organization_type", ""),
            fstek_117_class=classification.get("fstek_117_class", ""),
            has_dsp=classification.get("has_dsp", False),
            ispdn_category=classification.get("ispdn_category", ""),
            ispdn_subjects_count=classification.get("ispdn_subjects_count", 0),
            threat_type=classification.get("threat_type", ""),
            pp1119_level=classification.get("pp1119_level", ""),
        )
        
        queries = profile.get_search_queries()
        all_requirements = {}
        
        for query in queries:
            try:
                qe = self.embeddings.embed_query(query)
                results = self.collection.query(query_embeddings=[qe], n_results=5)
                for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                    req_id = meta.get("paragraph_id", "unknown")
                    if req_id not in all_requirements:
                        all_requirements[req_id] = {
                            "paragraph_id": req_id,
                            "source_document": meta.get("source", "unknown"),
                            "text": doc,
                        }
            except Exception as e:
                print(f"⚠️ Ошибка поиска: {e}")
        
        return list(all_requirements.values())
    
    def audit_system(self, pak_data: dict) -> dict:
        """
        Выполняет системный аудит ПАК как единого комплекса.
        Возвращает полный результат аудита.
        """
        classification = pak_data.get("classification", {})
        requirements = self.extract_requirements(classification)
        system_description = self.build_system_description(pak_data)
        
        print(f"🔍 Найдено требований: {len(requirements)}")
        print(f"📋 Анализ ПАК как единого комплекса...")
        
        # Системный промпт для комплексного аудита
        system_prompt = """Ты — ведущий эксперт-аудитор ФСТЭК России с 15-летним опытом аттестации ПАК.

ТЫ АНАЛИЗИРУЕШЬ ПАК КАК ЕДИНЫЙ КОМПЛЕКС, А НЕ НАБОР РАЗРОЗНЕННЫХ КОМПОНЕНТОВ.

ВАЖНЫЕ ПРИНЦИПЫ АНАЛИЗА:
1. Компоненты ПАК взаимосвязаны: одни защищают, другие компенсируют, третьи дублируют.
2. Если требование выполнено хотя бы одним компонентом — оно выполнено для всего ПАК.
3. Учитывай эшелонирование: защита на разных уровнях (физическом, сетевом, ОС, приложений, данных).
4. Оценивай комплексный эффект, а не сумму отдельных частей.

ФОРМАТ ОТВЕТА — СТРОГО JSON:
{
  "requirement_analysis": {
    "пункт_НПА": {
      "status": "COMPLIANT|NON_COMPLIANT|PARTIALLY_COMPLIANT",
      "compliance_level_pct": 0-100,
      "analysis": "Комплексный анализ выполнения требования ВСЕМ ПАК",
      "compensating_measures": "Какие компоненты компенсируют недостатки",
      "gaps": "Какие аспекты требования не выполнены ни одним компонентом",
      "recommendation": "Конкретная рекомендация по доработке КОМПЛЕКСА",
      "responsible_components": ["Список компонентов, отвечающих за требование"]
    }
  },
  "overall_assessment": {
    "total_requirements": N,
    "fully_compliant": N,
    "partially_compliant": N,
    "non_compliant": N,
    "overall_compliance_pct": 0-100,
    "critical_gaps": ["Список критических несоответствий"],
    "summary": "Общее заключение о состоянии защищённости ПАК"
  },
  "target_configuration": {
    "description": "Целевая конфигурация ПАК, обеспечивающая 100% соответствие",
    "changes_required": [
      {
        "component": "Компонент",
        "change": "Описание изменения",
        "requirement": "Ссылка на пункт НПА",
        "priority": "HIGH|MEDIUM|LOW"
      }
    ],
    "verification_method": "Метод проверки достижения 100% соответствия"
  },
  "test_program": {
    "test_scenarios": [
      {
        "scenario_id": "ТП-001",
        "requirement": "Ссылка на НПА",
        "description": "Описание сценария испытаний",
        "method": "Методика проверки",
        "expected_result": "Ожидаемый результат",
        "tools": ["Необходимые инструменты"]
      }
    ]
  }
}
"""
        
        user_prompt = f"""ПРОВЕДИ СИСТЕМНЫЙ АУДИТ ПАК КАК ЕДИНОГО КОМПЛЕКСА.

## КЛАССИФИКАЦИЯ СИСТЕМЫ
{json.dumps(classification, ensure_ascii=False, indent=2)}

## ПЕРЕЧЕНЬ ТРЕБОВАНИЙ НПА
{json.dumps([{'id': r['paragraph_id'], 'doc': r['source_document'], 'text': r['text'][:300]} for r in requirements], ensure_ascii=False, indent=2)}

## ОПИСАНИЕ ПАК КАК ЕДИНОГО КОМПЛЕКСА
{system_description}

## ЗАДАНИЕ
1. Проанализируй ПАК КАК ЕДИНОЕ ЦЕЛОЕ на соответствие каждому требованию.
2. Учитывай взаимосвязи: одни компоненты защищают, другие компенсируют, третьи дублируют.
3. Сформируй целевую конфигурацию для достижения 100% соответствия.
4. Разработай программу и методику испытаний.
"""
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
                # Парсинг JSON с восстановлением оборванного ответа
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            print("⚠️ JSON повреждён, пытаюсь восстановить...")
            import re
            
            result = {}
            
            # Извлекаем requirement_analysis
            match = re.search(r'"requirement_analysis"\s*:\s*\{', content)
            if match:
                depth = 0
                for i, ch in enumerate(content[match.start():]):
                    if ch == '{': depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            try:
                                ra_block = content[match.start():match.start()+i+1]
                                ra = json.loads('{' + ra_block + '}')
                                result["requirement_analysis"] = ra.get("requirement_analysis", {})
                            except:
                                pass
                            break
            
            # Извлекаем overall_assessment
            match = re.search(r'"overall_assessment"\s*:\s*\{', content)
            if match:
                depth = 0
                for i, ch in enumerate(content[match.start():]):
                    if ch == '{': depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            try:
                                oa_block = content[match.start():match.start()+i+1]
                                oa = json.loads('{' + oa_block + '}')
                                result["overall_assessment"] = oa.get("overall_assessment", {})
                            except:
                                pass
                            break
            
            if not result.get("requirement_analysis"):
                result = {"error": "Не удалось распарсить ответ LLM", "raw": content[:2000]}
                print("❌ Восстановление не удалось")
            else:
                print(f"✅ JSON частично восстановлен: {len(result.get('requirement_analysis', {}))} требований")
        
        result["system_name"] = pak_data.get("system_name", "")
        result["components"] = pak_data.get("components", [])
        result["classification"] = classification
        result["requirements"] = requirements
        result["timestamp"] = datetime.now().isoformat()
        
        return result
    
    def generate_documents(self, audit_result: dict, output_dir: str = "reports") -> dict:
        """Генерирует полный пакет документов по результатам системного аудита"""
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        system_name = audit_result.get("system_name", "ПАК")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        documents = {}
        
        # Документ 1: Матрица требований
        doc1 = {
            "title": f"Матрица требований НПА для {system_name}",
            "classification": audit_result.get("classification", {}),
            "requirements": audit_result.get("requirements", []),
            "requirement_analysis": audit_result.get("requirement_analysis", {}),
            "overall_assessment": audit_result.get("overall_assessment", {}),
            "components": audit_result.get("components", []),
        }
        doc1_path = output_path / f"01_matrix_{system_name}_{timestamp}.json"
        with open(doc1_path, "w", encoding="utf-8") as f:
            json.dump(doc1, f, ensure_ascii=False, indent=2)
        documents["matrix"] = str(doc1_path)
        
        # Документ 2: Ведомость несоответствий
        gaps = []
        analysis = audit_result.get("requirement_analysis", {})
        for req_id, data in analysis.items():
            if data.get("status") in ["NON_COMPLIANT", "PARTIALLY_COMPLIANT"]:
                gaps.append({
                    "requirement_id": req_id,
                    "status": data.get("status"),
                    "compliance_pct": data.get("compliance_level_pct", 0),
                    "gap_description": data.get("gaps", ""),
                    "compensating_measures": data.get("compensating_measures", ""),
                    "recommendation": data.get("recommendation", ""),
                })
        
        doc2 = {
            "title": f"Ведомость несоответствий для {system_name}",
            "total_gaps": len(gaps),
            "gaps": gaps,
            "overall_assessment": audit_result.get("overall_assessment", {}),
            "components": audit_result.get("components", []),
        }
        doc2_path = output_path / f"02_gaps_{system_name}_{timestamp}.json"
        with open(doc2_path, "w", encoding="utf-8") as f:
            json.dump(doc2, f, ensure_ascii=False, indent=2)
        documents["gaps"] = str(doc2_path)
        
        # Документ 3: Целевая конфигурация
        doc3 = {
            "title": f"Целевая конфигурация {system_name} (100% соответствие)",
            "system_name": system_name,
            "classification": audit_result.get("classification", {}),
            "description": audit_result.get("target_configuration", {}).get("description", ""),
            "changes": audit_result.get("target_configuration", {}).get("changes_required", []),
        }
        doc3_path = output_path / f"03_target_config_{system_name}_{timestamp}.json"
        with open(doc3_path, "w", encoding="utf-8") as f:
            json.dump(doc3, f, ensure_ascii=False, indent=2)
        documents["target_config"] = str(doc3_path)
        
        # Документ 4: Программа и методика испытаний
        doc4 = {
            "title": f"Программа и методика испытаний {system_name}",
            "classification": audit_result.get("classification", {}),
            "test_scenarios": audit_result.get("test_program", {}).get("test_scenarios", []),
        }
        doc4_path = output_path / f"04_test_program_{system_name}_{timestamp}.json"
        with open(doc4_path, "w", encoding="utf-8") as f:
            json.dump(doc4, f, ensure_ascii=False, indent=2)
        documents["test_program"] = str(doc4_path)
        
        # Документ 5: Заключение
        overall = audit_result.get("overall_assessment", {})
        doc5 = {
            "title": f"Заключение о соответствии {system_name} требованиям ФСТЭК",
            "system_name": system_name,
            "classification": audit_result.get("classification", {}),
            "compliance_pct": overall.get("overall_compliance_pct", 0),
            "conclusion": "СООТВЕТСТВУЕТ" if overall.get("overall_compliance_pct", 0) >= 100 else "ТРЕБУЕТ ДОРАБОТКИ",
            "critical_gaps": overall.get("critical_gaps", []),
            "summary": overall.get("summary", ""),
            "recommendation": "Рекомендуется к аттестации после устранения выявленных несоответствий" if overall.get("overall_compliance_pct", 0) < 100 else "Рекомендуется к аттестации",
        }
        doc5_path = output_path / f"05_conclusion_{system_name}_{timestamp}.json"
        with open(doc5_path, "w", encoding="utf-8") as f:
            json.dump(doc5, f, ensure_ascii=False, indent=2)
        documents["conclusion"] = str(doc5_path)
        
        return documents


# ========== Запуск ==========
if __name__ == "__main__":
    import sys
    
    json_path = sys.argv[1] if len(sys.argv) > 1 else "input_data.json"
    
    with open(json_path, "r", encoding="utf-8") as f:
        pak_data = json.load(f)
    
    auditor = SystemAuditor()
    
    print("=" * 60)
    print("🚀 СИСТЕМНЫЙ АУДИТ ПАК")
    print("=" * 60)
    
    result = auditor.audit_system(pak_data)
    
    print("\n📄 Генерация пакета документов...")
    documents = auditor.generate_documents(result)
    
    print("\n✅ Аудит завершён. Созданы документы:")
    for doc_type, path in documents.items():
        print(f"  📄 {doc_type}: {path}")
    
    # Сохраняем полный результат
    output_path = Path("reports") / f"system_audit_{pak_data.get('system_name', 'PAK')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n📦 Полный отчёт: {output_path}")
