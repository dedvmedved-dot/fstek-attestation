import json, sys, time, zipfile, pickle
from pathlib import Path
from datetime import datetime
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

from llm_adapter import LLMFactory
from chromadb import HttpClient
from chromadb.config import Settings
from classification_schema import ClassificationProfile
from langchain_core.messages import HumanMessage, SystemMessage

st.set_page_config(page_title="Аттестация ФСТЭК", page_icon="🛡️", layout="wide")
st.title("🛡️ Система подготовки к аттестации ФСТЭК")

# Сохранение/загрузка состояния
STATE_FILE = Path("reports") / ".streamlit_state.pkl"
def save_state():
    STATE_FILE.parent.mkdir(exist_ok=True)
    s = {}
    for k in ["audit_results", "system_audit_result", "system_audit_docs",
              "system_name", "classification", "components", "editable_components"]:
        if k in st.session_state: s[k] = st.session_state[k]
    with open(STATE_FILE, "wb") as f: pickle.dump(s, f)

def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "rb") as f: s = pickle.load(f)
            for k, v in s.items():
                if k not in st.session_state: st.session_state[k] = v
        except: pass

load_state()

if "audit_results" not in st.session_state: st.session_state.audit_results = None
if "audit_running" not in st.session_state: st.session_state.audit_running = False

# Боковая панель
with st.sidebar:
    st.header("📋 Классификация")
    system_name = st.text_input("Название системы", st.session_state.get("system_name", "ПАК-DRBD-2"))
    system_type = st.selectbox("Тип системы", ["ГИС", "ИСПДн", "КИИ", "АСУ ТП", "ГИС + ИСПДн"])
    fstek_117_class = st.selectbox("Класс по приказу №117", ["К1", "К2", "К3"])
    has_dsp = st.checkbox("Наличие ДСП", True)
    ispdn_category = st.selectbox("Категория ПДн", ["иные", "специальные", "биометрические", "общедоступные"])
    ispdn_subjects = st.number_input("Субъектов ПДн", 0, 10000000, 50000)
    threat_type = st.selectbox("Тип угроз", ["1-й тип", "2-й тип", "3-й тип"])
    pp1119_level = st.selectbox("Уровень по ПП №1119", ["УЗ-1", "УЗ-2", "УЗ-3", "УЗ-4"])
    st.divider()
    use_filter = st.checkbox("🎯 Умный фильтр требований", value=True)
    st.divider()
    uploaded_file = st.file_uploader("📂 Или загрузите input_data.json", type=["json"])
    
    if st.button("🚀 Запустить аудит", type="primary", use_container_width=True):
        st.session_state.audit_running = True
        st.session_state.audit_results = None

# Вкладки
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Покомпонентный", "🧩 Системный аудит", "📋 Компоненты", "💬 RAG-Чат", "📦 Отчёты и Архив"])

# Загрузка данных
if uploaded_file is not None:
    data = json.load(uploaded_file)
    classification = data.get("classification", {})
    components = data.get("components", [])
    system_name = data.get("system_name", system_name)
    st.session_state.classification = classification
    st.session_state.components = components
    st.session_state.system_name = system_name
    save_state()
else:
    classification = st.session_state.get("classification", {
        "system_type": system_type, "fstek_117_class": fstek_117_class,
        "has_dsp": has_dsp, "ispdn_category": ispdn_category,
        "ispdn_subjects_count": ispdn_subjects, "threat_type": threat_type,
        "pp1119_level": pp1119_level,
    })
    components = st.session_state.get("components", [])
    system_name = st.session_state.get("system_name", system_name)

normalized = []
for comp in components:
    normalized.append({
        "component_name": comp.get("component_name", comp.get("name", "")),
        "component_type": comp.get("component_type", comp.get("type", "")),
        "current_configuration": comp.get("configuration", comp.get("config", {})),
    })
if not normalized:
    normalized = [{"component_name": "Демо-компонент", "component_type": "ОС", "current_configuration": {"demo": True}}]

# ==================== ЗАПУСК АУДИТА ====================
if st.session_state.audit_running and st.session_state.audit_results is None:
    progress_container = st.container()
    with progress_container:
        st.markdown("### 🔍 Ход аудита")
        step1_status = st.empty()
        step1_status.info("⏳ Этап 1: Поиск требований в НПА...")
        progress_bar = st.progress(0, text="Подготовка...")
        
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
        
        client = HttpClient(host="localhost", port=8001, settings=Settings(anonymized_telemetry=False))
        collection = client.get_collection("fstek_npa")
        emb = LLMFactory.get_embeddings()
        search_queries = profile.get_search_queries()
        all_requirements = {}
        
        for i, query in enumerate(search_queries):
            progress_bar.progress((i+1)/(len(search_queries)+len(normalized)*5), text=f"Поиск: {query[:60]}...")
            try:
                qe = emb.embed_query(query)
                results = collection.query(query_embeddings=[qe], n_results=5)
                for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                    req_id = meta.get("paragraph_id", "unknown")
                    if req_id not in all_requirements:
                        all_requirements[req_id] = {"paragraph_id": req_id, "source_document": meta.get("source", "unknown"), "text": doc}
            except Exception as e:
                st.warning(f"⚠️ {e}")
        
        requirements = list(all_requirements.values())
        step1_status.success(f"✅ Найдено {len(requirements)} требований")
        
        if use_filter:
            from classification_schema import filter_requirements
            filtered_pairs = filter_requirements(requirements, normalized)
        else:
            filtered_pairs = [(req, comp) for req in requirements for comp in normalized]
        
        total_steps = len(filtered_pairs)
        step2_status = st.empty()
        step2_status.info(f"⏳ Аудит {total_steps} комбинаций...")
        
        AUDITOR_PROMPT = """Ты — эксперт-аудитор ФСТЭК. Верни JSON:
{"compliance_status":"COMPLIANT|NON_COMPLIANT|NEED_MORE_INFO","analysis":{"current_state":"...","gap":"...","risk_level":"HIGH|MEDIUM|LOW"},"developer_note":"...","recommended_configuration_change":{"action":"ENABLE|DISABLE|INSTALL|CONFIGURE","target":"...","new_value":"...","justification":"..."}}"""
        
        llm = LLMFactory.get_llm(mode="audit", temperature=0.1)
        audit_results = []
        
        for step_count, (req, comp) in enumerate(filtered_pairs, 1):
            progress_bar.progress((len(search_queries)+step_count)/(len(search_queries)+total_steps),
                                  text=f"Аудит {step_count}/{total_steps}: {req['paragraph_id']} → {comp['component_name'][:30]}")
            
            prompt = f"""Классификация: {classification}
Требование: {req['paragraph_id']} ({req['source_document']})
Текст: {req['text'][:2000]}
Компонент: {comp['component_name']}
Конфигурация: {json.dumps(comp.get('current_configuration', {}), ensure_ascii=False)}"""
            
            try:
                response = llm.invoke([SystemMessage(content=AUDITOR_PROMPT), HumanMessage(content=prompt)])
                content = response.content
                if "```json" in content: content = content.split("```json")[1].split("```")[0]
                elif "```" in content: content = content.split("```")[1].split("```")[0]
                result = json.loads(content)
            except:
                result = {"compliance_status": "ERROR"}
            result["requirement_id"] = req["paragraph_id"]
            result["source_document"] = req["source_document"]
            result["component_name"] = comp["component_name"]
            result["requirement_text"] = req["text"][:500]
            audit_results.append(result)
        
        step2_status.success("✅ Аудит завершён")
        progress_bar.progress(1.0, text="Готово!")
        st.session_state.audit_results = audit_results
        st.session_state.audit_running = False
        save_state()
        time.sleep(1)
        progress_container.empty()
        st.rerun()

# ==================== TAB1: ПОКОМПОНЕНТНЫЙ ====================
with tab3:
    if st.session_state.audit_results:
        results = st.session_state.audit_results
        st.header("📊 Результаты покомпонентного аудита")
        
        compliant = [r for r in results if r.get("compliance_status") == "COMPLIANT"]
        non_compliant = [r for r in results if r.get("compliance_status") == "NON_COMPLIANT"]
        need_info = [r for r in results if r.get("compliance_status") == "NEED_MORE_INFO"]
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("✅ Соответствует", len(compliant))
        c2.metric("❌ Не соответствует", len(non_compliant))
        c3.metric("❓ Уточнить", len(need_info))
        c4.metric("📋 Всего", len(results))
        
        if results:
            st.progress(len(compliant)/len(results), text=f"Соответствие: {len(compliant)/len(results):.0%}")
        
        st.divider()
        status_filter = st.multiselect("Фильтр", ["COMPLIANT", "NON_COMPLIANT", "NEED_MORE_INFO"], default=["NON_COMPLIANT"])
        for item in [r for r in results if r.get("compliance_status") in status_filter]:
            status = item.get("compliance_status", "")
            icon = {"COMPLIANT": "✅", "NON_COMPLIANT": "❌", "NEED_MORE_INFO": "❓"}.get(status, "")
            with st.expander(f"{icon} {item.get('requirement_id','?')} — {item.get('component_name','?')}", expanded=(status=="NON_COMPLIANT")):
                st.write(f"**Источник:** {item.get('source_document','')}")
                if "analysis" in item:
                    st.write(f"**Состояние:** {item['analysis'].get('current_state','')}")
                    st.write(f"**Недостаток:** {item['analysis'].get('gap','')}")
                if "recommended_configuration_change" in item:
                    st.write(f"**Действие:** `{item['recommended_configuration_change'].get('action','')}` — {item['recommended_configuration_change'].get('new_value','')}")
                if "developer_note" in item:
                    st.write(f"**Замечание:** {item['developer_note']}")
    else:
        st.info("Запустите аудит в боковой панели или перейдите на вкладку «Системный аудит».")

# ==================== TAB2: СИСТЕМНЫЙ АУДИТ ====================
with tab2:
    st.header("🧩 Системный аудит ПАК")
    st.markdown("Анализ ПАК как **единого комплекса** с учётом взаимосвязей, компенсации и эшелонирования.")
    
    if st.button("🚀 Запустить системный аудит", type="primary"):
        with st.spinner("🔍 Системный анализ ПАК..."):
            from system_audit import SystemAuditor
            pak_data = {"system_name": system_name, "classification": classification, "components": components if components else normalized, "protected_info": {}}
            auditor = SystemAuditor()
            result = auditor.audit_system(pak_data)
            documents = auditor.generate_documents(result)
            st.session_state.system_audit_result = result
            st.session_state.system_audit_docs = documents
            save_state()
            st.rerun()
    
    if st.session_state.get("system_audit_result"):
        result = st.session_state.system_audit_result
        overall = result.get("overall_assessment", {})
        target = result.get("target_configuration", {})
        test_prog = result.get("test_program", {})
        
        st.divider()
        st.subheader("📊 Общая оценка")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Всего требований", overall.get("total_requirements", 0))
        c2.metric("✅ Полностью", overall.get("fully_compliant", 0))
        c3.metric("⚠️ Частично", overall.get("partially_compliant", 0))
        c4.metric("📈 Соответствие", f"{overall.get('overall_compliance_pct', 0)}%")
        
        if overall.get("critical_gaps"):
            st.error("🚨 Критические несоответствия:")
            for gap in overall["critical_gaps"]: st.write(f"- {gap}")
        st.info(overall.get("summary", ""))
        
        st.divider()
        st.subheader("🎯 Целевая конфигурация (100% соответствие)")
        for change in target.get("changes_required", target.get("changes", [])):
            priority = change.get("priority", "MEDIUM")
            icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(priority, "⚪")
            with st.expander(f"{icon} {change.get('component', '')}: {change.get('change', '')[:80]}..."):
                st.write(f"**Изменение:** {change.get('change', '')}")
                st.write(f"**Требование:** {change.get('requirement', '')}")
        
        st.divider()
        st.subheader("🧪 Программа испытаний")
        for s in test_prog.get("test_scenarios", [])[:5]:
            with st.expander(f"📋 {s.get('scenario_id', '')}: {s.get('description', '')[:80]}..."):
                st.write(f"**Методика:** {s.get('method', '')}")
                st.write(f"**Результат:** {s.get('expected_result', '')}")

# ==================== TAB3: КОМПОНЕНТЫ ====================
with tab4:
    from streamlit_chat import render_chat_tab
    render_chat_tab()

# ==================== TAB4: ОТЧЁТЫ И АРХИВ ====================
with tab1:
    st.header("📋 Компоненты системы")
    
    if "editable_components" not in st.session_state:
        st.session_state.editable_components = normalized.copy()
    
    comps = st.session_state.editable_components
    st.write(f"**Всего компонентов: {len(comps)}**")
    
    ca, cs, cr = st.columns(3)
    with ca:
        if st.button("➕ Добавить", use_container_width=True):
            st.session_state.editable_components.append({"component_name": "Новый", "component_type": "", "current_configuration": {}})
            st.rerun()
    with cs:
        if st.button("💾 Сохранить JSON", use_container_width=True):
            data = {"system_name": system_name, "classification": classification, "components": [{"component_name": c["component_name"], "component_type": c.get("component_type", ""), "configuration": c.get("current_configuration", {})} for c in comps]}
            with open("input_data.json", "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
            st.success("✅ Сохранено в input_data.json")
    with cr:
        if st.button("🔄 Сбросить", use_container_width=True):
            st.session_state.editable_components = normalized.copy()
            st.rerun()
    
    st.divider()
    for i, comp in enumerate(comps):
        with st.expander(f"🖥️ {comp.get('component_name', f'Компонент {i+1}')} — {comp.get('component_type', 'тип не указан')}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                new_name = st.text_input("Название", value=comp.get("component_name", ""), key=f"name_{i}")
                new_type = st.text_input("Тип", value=comp.get("component_type", ""), key=f"type_{i}")
                config = comp.get("current_configuration", {})
                for j, (k, v) in enumerate(list(config.items())):
                    ck, cv, cd = st.columns([2, 3, 1])
                    with ck: nk = st.text_input("Параметр", value=k, key=f"key_{i}_{j}")
                    with cv: nv = st.text_input("Значение", value=str(v), key=f"val_{i}_{j}")
                    with cd:
                        if st.button("🗑️", key=f"del_{i}_{j}"): config.pop(k, None); st.rerun()
                    if nk and k not in [x for x in config if x != k]: config[nk] = nv
                cnk, cnv, cna = st.columns([2, 3, 1])
                with cnk: npk = st.text_input("Параметр", key=f"new_key_{i}")
                with cnv: npv = st.text_input("Значение", key=f"new_val_{i}")
                with cna:
                    if st.button("➕", key=f"add_{i}") and npk:
                        config[npk] = npv; st.rerun()
                st.session_state.editable_components[i] = {"component_name": new_name, "component_type": new_type, "current_configuration": config}
            with c2:
                if st.button("🗑️ Удалить", key=f"del_comp_{i}"):
                    st.session_state.editable_components.pop(i); st.rerun()

with tab5:
    from streamlit_archive import render_archive_tab
    render_archive_tab()
