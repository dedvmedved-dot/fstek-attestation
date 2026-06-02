"""Вкладка RAG-чата для Streamlit с историей чатов."""
import streamlit as st
from rag_chat import RAGChat
from pathlib import Path
import tempfile
from datetime import datetime
import json

CHATS_DIR = Path("chats")
CHATS_DIR.mkdir(exist_ok=True)

def render_chat_tab():
    st.header("💬 RAG-Чат")
    
    chat_files = sorted(CHATS_DIR.glob("chat_*.json"), reverse=True)
    chat_names = {}
    for cf in chat_files:
        try:
            with open(cf) as f:
                data = json.load(f)
            chat_names[cf.stem] = f"{data.get('created','')[:16]} | {data.get('name','')[:40]}"
        except:
            chat_names[cf.stem] = cf.stem
    
    with st.sidebar:
        st.subheader("💾 Чаты")
        if st.button("➕ Новый чат", use_container_width=True):
            if "rag_chat" in st.session_state and st.session_state.rag_chat.get_history():
                _save_chat(st.session_state.rag_chat)
            st.session_state.rag_chat = RAGChat()
            st.rerun()
        
        selected = st.selectbox("История", ["текущий"] + list(chat_names.keys()),
                               format_func=lambda x: "🟢 Текущий" if x=="текущий" else chat_names.get(x,x))
        
        if selected != "текущий" and selected in chat_names:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📂 Загрузить", use_container_width=True):
                    with open(CHATS_DIR / f"{selected}.json") as f:
                        data = json.load(f)
                    chat = RAGChat()
                    chat.chat_history = data.get("history", [])
                    st.session_state.rag_chat = chat
                    st.rerun()
            with c2:
                if st.button("🗑️", use_container_width=True):
                    (CHATS_DIR / f"{selected}.json").unlink()
                    st.rerun()
    
    if "rag_chat" not in st.session_state:
        st.session_state.rag_chat = RAGChat()
    chat = st.session_state.rag_chat
    
    with st.sidebar:
        st.divider()
        provider = st.selectbox("Провайдер", list(RAGChat.PROVIDERS.keys()),
                               format_func=lambda x: RAGChat.PROVIDERS[x]["name"], key="cp")
        model = st.selectbox("Модель", list(RAGChat.PROVIDERS[provider]["models"].keys()), key="cm")
        uploaded_files = st.file_uploader("📎 Файлы", type=["pdf","docx","xlsx","md","txt","json"],
                                         accept_multiple_files=True, key="cf")
        if st.button("🗑️ Очистить историю", use_container_width=True):
            chat.clear_history()
            st.rerun()
        
        st.divider()
        st.subheader("📄 Просмотр документов")
        all_sources = chat.get_all_sources()
        doc_choice = st.selectbox("Документ", ["—"] + all_sources, key="doc_sel")
        
        if doc_choice != "—":
            docs = chat.search_by_document(doc_choice)
            total = max(len(docs), 1)
            pages = max(1, (total-1)//20+1)
            if pages > 1:
                page = st.slider("Страница", 1, pages, 1, key=f"pg_{doc_choice}")
            else:
                page = 1
                st.write("Страница 1 из 1")
            st.write(f"Строки {(page-1)*20+1}-{min(page*20, total)} из {total}")
            if st.button(f"📖 Показать (стр. {page})", use_container_width=True, key=f"btn_{doc_choice}"):
                chunks = docs[(page-1)*20:page*20]
                text = "\n\n".join(d["text"] for d in chunks)
                chat.chat_history.append({"role": "user", "content": f"📄 {doc_choice}, стр. {page}"})
                chat.chat_history.append({"role": "assistant", "content": text})
                _save_chat(chat)
                st.markdown('<div id="bottom"></div>', unsafe_allow_html=True)
                st.markdown('<script>document.getElementById("bottom").scrollIntoView({behavior:"smooth"});</script>', unsafe_allow_html=True)
                st.rerun()
    
    for msg in chat.get_history():
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(msg["content"])
    
    if prompt := st.chat_input("Вопрос..."):
        with st.chat_message("user"):
            st.write(prompt)
        
        temp_files = []
        if uploaded_files:
            for uf in uploaded_files:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(uf.name).suffix)
                tmp.write(uf.getbuffer())
                tmp.close()
                temp_files.append(tmp.name)
        
        with st.chat_message("assistant"):
            with st.spinner("Поиск..."):
                result = chat.chat(prompt, provider=provider, model=model,
                                  files=temp_files if temp_files else None)
                st.markdown(result["reply"])
        
        for tf in temp_files:
            Path(tf).unlink(missing_ok=True)
        _save_chat(chat)
        # Якорь для автоскролла
        st.markdown('<div id="bottom"></div>', unsafe_allow_html=True)
        st.markdown('<script>document.getElementById("bottom").scrollIntoView({behavior:"smooth"});</script>', unsafe_allow_html=True)
        st.rerun()


def _save_chat(chat):
    if not chat.get_history():
        return
    name = "".join(c for c in chat.get_history()[0]["content"][:50] if c.isalnum() or c in " _-").strip() or "чат"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (CHATS_DIR / f"chat_{ts}.json").write_text(json.dumps({
        "name": name, "created": datetime.now().isoformat(),
        "history": chat.get_history(), "last_doc": chat._last_opened_doc,
    }, ensure_ascii=False, indent=2))
