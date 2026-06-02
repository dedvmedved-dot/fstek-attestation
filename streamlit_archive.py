"""Модуль архива для Streamlit."""
from pathlib import Path
from collections import defaultdict
import streamlit as st
import json
import re

def render_archive_tab():
    st.header("📦 Отчёты и Архив")
    reports_dir = Path("reports")
    
    # === Сбор всех сессий ===
    sessions = {}
    
    # 1. Одиночные system_audit_*.json
    for f in sorted(reports_dir.glob("system_audit_*.json"), reverse=True):
        ts = f.stem.replace("system_audit_", "")
        try:
            with open(f) as fh:
                sa = json.load(fh)
            sn = sa.get("system_name", ts)
        except:
            sn = ts
        key = f"single_{ts}"
        sessions[key] = {
            "type": "single", "key": key, "system_audit": str(f),
            "sn": sn, "ts": ts, "dir": reports_dir
        }
    
    # 2. Пакетные batch_*
    for batch_dir in sorted(reports_dir.glob("batch_*"), reverse=True):
        for session_dir in sorted(batch_dir.glob("*"), reverse=True):
            if not session_dir.is_dir():
                continue
            sa_file = session_dir / "system_audit.json"
            if not sa_file.exists():
                continue
            
            ts = session_dir.name
            try:
                with open(sa_file) as fh:
                    sa = json.load(fh)
                cls = sa.get("classification", {})
                sys_type = cls.get("system_type", "").split()[0]
                cls_name = cls.get("fstek_117_class", "")
                pp = cls.get("pp1119_level", "")
                dsp = "ДСП" if cls.get("has_dsp") else ""
                parts = [p for p in [sys_type, cls_name, pp, dsp] if p]
                sn = f"{sa.get('system_name', 'ПАК')} | {' / '.join(parts)}"
            except:
                sn = ts
            
            key = f"batch_{batch_dir.name}_{session_dir.name}"
            sessions[key] = {
                "type": "batch", "key": key, "system_audit": str(sa_file),
                "sn": sn, "ts": ts, "dir": session_dir
            }
    
    if not sessions:
        st.info("📭 Архив пуст.")
        return
    
    # === Выбор сессии ===
    session_list = []
    for key, sess in sorted(sessions.items(), reverse=True):
        oa = {}
        sa_path = sess.get("system_audit", "")
        if sa_path and Path(sa_path).exists():
            try:
                with open(sa_path) as f:
                    oa = json.load(f).get("overall_assessment", {})
            except:
                pass
        
        sn = sess["sn"]
        ts = sess["ts"]
        comp = oa.get("fully_compliant", 0)
        total = oa.get("total_requirements", 0)
        pct = oa.get("overall_compliance_pct", 0)
        
        # Дата из имени папки batch или из ts
        try:
            date_str = ts[:8] if sess["type"] == "single" else sess["dir"].parent.name.replace("batch_", "")
            dt = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:8]}"
        except:
            dt = ts[:16]
        
        session_list.append({
            "key": key, "sn": sn, "ts": ts, "dt": dt,
            "comp": comp, "total": total, "pct": pct,
            "type": sess["type"], "dir": sess["dir"],
            "system_audit": sa_path,
        })
    
    idx = st.selectbox(
        "Выберите сессию аудита:",
        range(len(session_list)),
        format_func=lambda i: f"{session_list[i]['dt']} — {session_list[i]['sn']} ({session_list[i]['comp']}/{session_list[i]['total']}, {session_list[i]['pct']}%)"
    )
    
    sel = session_list[idx]
    session_dir = sel["dir"]
    sa_path = sel["system_audit"]
    
    # === Сводка ===
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Система", sel["sn"])
    c2.metric("Требований", sel["total"])
    c3.metric("Соответствует", sel["comp"])
    c4.metric("%", f"{sel['pct']}%")
    
    # === Документы сессии ===
    st.divider()
    st.subheader("📄 Документы сессии")
    
    prefixes = ["01_matrix", "02_gaps", "03_target_config", "04_test_program", "05_conclusion"]
    labels = ["📋 Матрица", "❌ Несоотв.", "🎯 Целевая КФГ", "🧪 Испытания", "📝 Заключение"]
    
    # Для batch — ищем файлы в session_dir
    if sel["type"] == "batch":
        file_map = {}
        for prefix in prefixes:
            found = list(session_dir.glob(f"{prefix}_*")) + list(session_dir.glob(f"{prefix}.*"))
            if found:
                file_map[prefix] = str(found[0])
        
        cols = st.columns(5)
        for i, (prefix, label) in enumerate(zip(prefixes, labels)):
            with cols[i]:
                fpath = file_map.get(prefix, "")
                if fpath and Path(fpath).exists():
                    with open(fpath, "rb") as fh:
                        st.download_button(label, fh.read(), file_name=Path(fpath).name,
                                         mime="application/json", use_container_width=True,
                                         key=f"dl_{sel['ts']}_{prefix}")
                else:
                    st.caption(f"{label}\n—")
    else:
        # Для single — старый поиск по ts
        file_map = {}
        for prefix in prefixes:
            found = list(reports_dir.glob(f"{prefix}_*{sel['ts']}*.json"))
            if found:
                file_map[prefix] = str(found[0])
        
        cols = st.columns(5)
        for i, (prefix, label) in enumerate(zip(prefixes, labels)):
            with cols[i]:
                fpath = file_map.get(prefix, "")
                if fpath and Path(fpath).exists():
                    with open(fpath, "rb") as fh:
                        st.download_button(label, fh.read(), file_name=Path(fpath).name,
                                         mime="application/json", use_container_width=True,
                                         key=f"dl_{sel['ts']}_{prefix}")
                else:
                    st.caption(f"{label}\n—")
    
    # === Офисные форматы ===
    st.divider()
    st.subheader("📄 Офисные форматы")
    
    if sel["type"] == "batch":
        # Ищем в session_dir
        docx_files = list(session_dir.glob("protocol_*.docx"))
        xlsx_files = list(session_dir.glob("matrix_*.xlsx"))
    else:
        docx_files = list(reports_dir.glob(f"protocol_*{sel['ts']}*.docx"))
        xlsx_files = list(reports_dir.glob(f"matrix_*{sel['ts']}*.xlsx"))
    
    cd, cx = st.columns(2)
    with cd:
        if docx_files:
            with open(docx_files[0], "rb") as fh:
                st.download_button("📥 Скачать DOCX", fh.read(), file_name=docx_files[0].name,
                                 mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                 key=f"dl_docx_{sel['ts']}")
        elif sa_path and Path(sa_path).exists():
            if st.button("🔄 Создать DOCX", key=f"gen_docx_{sel['ts']}"):
                from report_docx import FSTEKReportGenerator
                out = session_dir / f"protocol_{sel['sn'][:30]}.docx" if sel["type"] == "batch" else None
                FSTEKReportGenerator(sa_path).generate(str(out) if out else None)
                st.rerun()
    
    with cx:
        if xlsx_files:
            with open(xlsx_files[0], "rb") as fh:
                st.download_button("📥 Скачать XLSX", fh.read(), file_name=xlsx_files[0].name,
                                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 key=f"dl_xlsx_{sel['ts']}")
        elif sa_path and Path(sa_path).exists():
            if st.button("🔄 Создать XLSX", key=f"gen_xlsx_{sel['ts']}"):
                from report_xlsx import FSTEKExcelGenerator
                out = session_dir / f"matrix_{sel['sn'][:30]}.xlsx" if sel["type"] == "batch" else None
                FSTEKExcelGenerator(sa_path).generate(str(out) if out else None)
                st.rerun()
    
    # === Markdown / PDF ===
    st.divider()
    st.subheader("📝 Единый отчёт (Markdown / PDF)")
    
    if sa_path and Path(sa_path).exists():
        mc1, mc2 = st.columns(2)
        with mc1:
            if st.button("📝 Создать Markdown", key=f"md_{sel['ts']}", use_container_width=True):
                from report_markdown import generate_full_report_md
                md = generate_full_report_md(sa_path)
                safe = sel['sn'][:30].replace('/', '_').replace('|', '_').replace(' ', '_').strip('_')
                out = session_dir / f"full_report_{safe}.md" if sel["type"] == "batch" else Path(sa_path).with_suffix('.md')
                out.write_text(md, encoding='utf-8')
                st.success("Markdown создан")
                st.rerun()
        with mc2:
            if st.button("📄 Создать PDF", key=f"pdf_{sel['ts']}", use_container_width=True):
                from report_markdown import generate_full_report_pdf
                safe = sel['sn'][:30].replace('/', '_').replace('|', '_').replace(' ', '_').strip('_')
                out = session_dir / f"full_report_{safe}.pdf" if sel["type"] == "batch" else None
                try:
                    generate_full_report_pdf(sa_path, str(out) if out else None)
                    st.success("PDF создан")
                except Exception as e:
                    st.error(f"Ошибка PDF: {e}")
                st.rerun()
    
    # Показать существующие
    # Ищем MD/PDF в папке сессии
    if sel["type"] == "batch":
        md_files = list(session_dir.glob("*.md"))
        pdf_files = list(session_dir.glob("*.pdf"))
    else:
        md_files = list(reports_dir.glob(f"full_report_*{sel['ts']}*.md"))
        pdf_files = list(reports_dir.glob(f"full_report_*{sel['ts']}*.pdf"))
    # Добавляем поиск в текущей папке для batch
    if sel["type"] == "batch":
        md_files = list(session_dir.glob("*.md"))
        pdf_files = list(session_dir.glob("*.pdf"))
    
    for f in md_files:
        with open(f, "rb") as fh:
            st.download_button(f"📝 {f.name}", fh.read(), file_name=f.name, mime="text/markdown", key=f"dl_md_{f.name}")
    for f in pdf_files:
        with open(f, "rb") as fh:
            st.download_button(f"📄 {f.name}", fh.read(), file_name=f.name, mime="application/pdf", key=f"dl_pdf_{f.name}")
    
    # === SVG ===
    st.divider()
    st.subheader("📐 Целевая конфигурация (SVG)")
    
    svg_files = []
    tc_json = []
    if sel["type"] == "batch":
        svg_files = sorted(session_dir.glob("target_config_*.svg"), key=lambda x: x.stat().st_mtime, reverse=True)
        tc_json = list(session_dir.glob("03_target_config_*.json"))
    else:
        svg_files = list(reports_dir.glob(f"target_config_*{sel['ts']}*.svg"))
        tc_json = list(reports_dir.glob(f"03_target_config_*{sel['ts']}*.json"))
    
    if svg_files:
        with open(svg_files[0], "rb") as fh:
            st.download_button("📥 Скачать SVG", fh.read(), file_name=svg_files[0].name,
                             mime="image/svg+xml", key=f"dl_svg_{sel['ts']}")
    
    graph_source = str(tc_json[0]) if tc_json else sa_path
    if graph_source and Path(graph_source).exists():
        if st.button("🖼️ Пересоздать SVG", key=f"graph_{sel['ts']}"):
            from target_config_graph import generate_target_config_svg
            safe_name = sel['sn'][:30].replace('/', '_').replace('|', '_').replace(' ', '_').strip('_')
            out = session_dir / f"target_config_{safe_name}.svg" if sel["type"] == "batch" else None
            generate_target_config_svg(graph_source, str(out) if out else None)
            st.success("SVG создана")
            st.rerun()
    
    # === ZIP ===
    st.divider()
    st.subheader("📦 ZIP-пакет")
    
    zip_path = reports_dir / f"package_{sel['ts']}.zip"
    import zipfile
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        if sel["type"] == "batch":
            for ff in session_dir.glob("*"):
                if ff.is_file() and not ff.name.endswith('.zip'):
                    zf.write(ff, ff.name)
        else:
            for f in reports_dir.glob(f"*{sel['ts']}*"):
                if f.is_file() and 'batch_' not in str(f):
                    zf.write(f, f.name)
    
    with open(zip_path, "rb") as fh:
        st.download_button("📦 ZIP (все документы)", fh.read(), file_name=zip_path.name,
                         mime="application/zip", use_container_width=True, key=f"zip_{sel['ts']}")
    
    # === Очистка ===
    st.divider()
    with st.expander("🗑️ Управление архивом"):
        total_files = len(list(reports_dir.glob("**/*")))
        total_size = sum(f.stat().st_size for f in reports_dir.glob("**/*") if f.is_file()) / 1024 / 1024
        st.write(f"Файлов: {total_files}, Размер: {total_size:.1f} MB")
        if st.button("🗑️ Удалить ZIP-архивы"):
            for f in reports_dir.glob("package_*.zip"):
                f.unlink()
            st.success("ZIP удалены")
            st.rerun()
