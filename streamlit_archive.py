"""Модуль архива для Streamlit."""
from pathlib import Path
from collections import defaultdict
import streamlit as st
import json

def render_archive_tab():
    st.header("📦 Отчёты и Архив")
    reports_dir = Path("reports")
    
    if not reports_dir.exists() or not list(reports_dir.glob("system_audit_*.json")):
        st.info("📭 Архив пуст.")
        return
    
    # Группируем все файлы по system_name + временной метке из system_audit
    sessions = {}
    
    # Сначала собираем system_audit — они задают канонические ts
    for f in sorted(reports_dir.glob("system_audit_*.json"), reverse=True):
        ts = f.stem.replace("system_audit_", "")
        try:
            with open(f) as fh:
                sa = json.load(fh)
            sn = sa.get("system_name", ts)
        except:
            sn = ts
        key = f"{sn}_{ts}"
        if key not in sessions:
            sessions[key] = {"system_audit": str(f), "sn": sn, "ts": ts, "docs": {}}
    
    # Добавляем остальные файлы
    for prefix in ["01_matrix", "02_gaps", "03_target_config", "04_test_program", "05_conclusion"]:
        for f in sorted(reports_dir.glob(f"{prefix}_*.json"), reverse=True):
            f_ts = f.stem.replace(f"{prefix}_", "")
            # Ищем сессию с такой же ts
            for key, session in sessions.items():
                if session["ts"] == f_ts:
                    session["docs"][prefix] = str(f)
                    break
    
    if not sessions:
        st.info("📭 Архив пуст.")
        return
    
    # Список для selectbox
    session_list = []
    for key, sess in sorted(sessions.items(), reverse=True):
        sa_path = sess.get("system_audit", "")
        oa = {}
        if sa_path and Path(sa_path).exists():
            try:
                with open(sa_path) as f:
                    sa = json.load(f)
                oa = sa.get("overall_assessment", {})
            except:
                pass
        
        sn = sess["sn"]
        ts = sess["ts"]
        comp = oa.get("fully_compliant", 0)
        total = oa.get("total_requirements", 0)
        pct = oa.get("overall_compliance_pct", 0)
        dt = f"{ts[:4]}.{ts[4:6]}.{ts[6:8]} {ts[9:11]}:{ts[11:13]}" if len(ts) >= 13 else ts
        
        session_list.append({
            "key": key, "sn": sn, "ts": ts, "dt": dt,
            "comp": comp, "total": total, "pct": pct,
            "docs": sess["docs"],
            "system_audit": sa_path,
        })
    
    idx = st.selectbox(
        "Выберите сессию аудита:",
        range(len(session_list)),
        format_func=lambda i: f"{session_list[i]['dt']} — {session_list[i]['sn']} ({session_list[i]['comp']}/{session_list[i]['total']}, {session_list[i]['pct']}%)"
    )
    
    sel = session_list[idx]
    docs = sel["docs"]
    sa_path = sel["system_audit"]
    
    # Сводка
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Система", sel["sn"])
    c2.metric("Требований", sel["total"])
    c3.metric("Соответствует", sel["comp"])
    c4.metric("%", f"{sel['pct']}%")
    
    st.divider()
    st.subheader("📄 Документы сессии")
    
    # Таблица документов с конвертацией
    doc_list = [
        ("01_matrix", "📋 Матрица требований", "matrix"),
        ("02_gaps", "❌ Ведомость несоответствий", "gaps"),
        ("03_target_config", "🎯 Целевая конфигурация", "target"),
        ("04_test_program", "🧪 Программа испытаний", "test"),
        ("05_conclusion", "📝 Заключение", "conclusion"),
    ]
    
    for prefix, label, short in doc_list:
        fpath = docs.get(prefix, "")
        if not fpath or not Path(fpath).exists():
            st.caption(f"{label} — файл не найден")
            continue
        
        with st.expander(f"{label}", expanded=(prefix == "01_matrix")):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                with open(fpath, "rb") as fh:
                    st.download_button("📄 JSON", fh.read(), file_name=Path(fpath).name,
                                     mime="application/json", key=f"json_{sel['ts']}_{prefix}")
            
            with col2:
                if st.button("📝 MD", key=f"md_{sel['ts']}_{prefix}"):
                    from report_markdown import (
                        generate_matrix_md, generate_gaps_md, generate_target_md,
                        generate_test_md, generate_conclusion_md
                    )
                    generators = {
                        "01_matrix": generate_matrix_md,
                        "02_gaps": generate_gaps_md,
                        "03_target_config": generate_target_md,
                        "04_test_program": generate_test_md,
                        "05_conclusion": generate_conclusion_md,
                    }
                    md_content = generators[prefix](fpath)
                    md_path = Path(fpath).with_suffix('.md')
                    md_path.write_text(md_content, encoding='utf-8')
                    st.success(f"MD создан: {md_path.name}")
                    st.rerun()
            
            with col3:
                if st.button("📄 PDF", key=f"pdf_{sel['ts']}_{prefix}"):
                    from report_markdown import (
                        generate_matrix_md, generate_gaps_md, generate_target_md,
                        generate_test_md, generate_conclusion_md
                    )
                    import markdown
                    from weasyprint import HTML
                    
                    generators = {
                        "01_matrix": generate_matrix_md,
                        "02_gaps": generate_gaps_md,
                        "03_target_config": generate_target_md,
                        "04_test_program": generate_test_md,
                        "05_conclusion": generate_conclusion_md,
                    }
                    md_content = generators[prefix](fpath)
                    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{{font-family:'Times New Roman',serif;font-size:11pt;margin:1.5cm;}}
table{{border-collapse:collapse;width:100%;margin:8px 0;}}
th,td{{border:1px solid #333;padding:5px;font-size:9pt;}}
th{{background-color:#4472C4;color:white;}}</style></head>
<body>{markdown.markdown(md_content, extensions=['tables'])}</body></html>"""
                    pdf_path = Path(fpath).with_suffix('.pdf')
                    HTML(string=html).write_pdf(str(pdf_path))
                    st.success(f"PDF создан: {pdf_path.name}")
                    st.rerun()
            
            with col4:
                # Показываем ссылки на существующие MD/PDF
                md_file = Path(fpath).with_suffix('.md')
                pdf_file = Path(fpath).with_suffix('.pdf')
                if md_file.exists():
                    with open(md_file, "rb") as fh:
                        st.download_button("📥 MD", fh.read(), file_name=md_file.name,
                                         mime="text/markdown", key=f"dl_md_{sel['ts']}_{prefix}")
                if pdf_file.exists():
                    with open(pdf_file, "rb") as fh:
                        st.download_button("📥 PDF", fh.read(), file_name=pdf_file.name,
                                         mime="application/pdf", key=f"dl_pdf_{sel['ts']}_{prefix}")
    
    st.divider()
    st.subheader("📄 Офисные форматы")
    
    cd, cx = st.columns(2)
    with cd:
        if sa_path and Path(sa_path).exists():
            docx_files = sorted(reports_dir.glob("protocol_*.docx"), key=lambda x: x.stat().st_mtime, reverse=True)[:1]
            if docx_files:
                with open(docx_files[0], "rb") as fh:
                    st.download_button("📥 Скачать DOCX", fh.read(), file_name=docx_files[0].name,
                                     mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                     key=f"dl_docx_{sel['ts']}")
            else:
                if st.button("🔄 Создать DOCX", key=f"gen_docx_{sel['ts']}"):
                    from report_docx import FSTEKReportGenerator
                    FSTEKReportGenerator(sa_path).generate()
                    st.rerun()
    
    with cx:
        if sa_path and Path(sa_path).exists():
            xlsx_files = sorted(reports_dir.glob("matrix_*.xlsx"), key=lambda x: x.stat().st_mtime, reverse=True)[:1]
            if xlsx_files:
                with open(xlsx_files[0], "rb") as fh:
                    st.download_button("📥 Скачать XLSX", fh.read(), file_name=xlsx_files[0].name,
                                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                     key=f"dl_xlsx_{sel['ts']}")
            else:
                if st.button("🔄 Создать XLSX", key=f"gen_xlsx_{sel['ts']}"):
                    from report_xlsx import FSTEKExcelGenerator
                    FSTEKExcelGenerator(sa_path).generate()
                    st.rerun()
    
    st.divider()
    st.subheader("📝 Единый отчёт (Markdown / PDF)")
    
    if sa_path and Path(sa_path).exists():
        mc1, mc2 = st.columns(2)
        with mc1:
            if st.button("📝 Создать Markdown", key=f"md_{sel['ts']}", use_container_width=True):
                from report_markdown import generate_full_report_md
                md_content = generate_full_report_md(sa_path)
                md_path = reports_dir / f"full_report_{sel['sn']}_{sel['ts']}.md"
                md_path.write_text(md_content, encoding='utf-8')
                st.success("Markdown создан")
                st.rerun()
        with mc2:
            if st.button("📄 Создать PDF", key=f"pdf_{sel['ts']}", use_container_width=True):
                from report_markdown import generate_full_report_pdf
                try:
                    pdf_path = reports_dir / f"full_report_{sel['sn']}_{sel['ts']}.pdf"
                    generate_full_report_pdf(sa_path, str(pdf_path))
                    st.success(f"PDF создан: {pdf_path.name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")
    
    md_files = sorted(reports_dir.glob("full_report_*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:3]
    pdf_files = sorted(reports_dir.glob("full_report_*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True)[:3]
    
    for f in md_files:
        with open(f, "rb") as fh:
            st.download_button(f"📝 {f.name}", fh.read(), file_name=f.name, mime="text/markdown", key=f"dl_md_{f.name}")
    for f in pdf_files:
        with open(f, "rb") as fh:
            st.download_button(f"📄 {f.name}", fh.read(), file_name=f.name, mime="application/pdf", key=f"dl_pdf_{f.name}")
    
    st.divider()
    st.subheader("📐 Целевая конфигурация (SVG)")
    
    tc_path = docs.get("03_target_config", sa_path)
    if tc_path and Path(tc_path).exists():
        svg_files = sorted(reports_dir.glob("target_config_*.svg"), key=lambda x: x.stat().st_mtime, reverse=True)[:1]
        if svg_files:
            with open(svg_files[0], "rb") as fh:
                st.download_button("📥 Скачать SVG", fh.read(), file_name=svg_files[0].name, mime="image/svg+xml", key=f"dl_svg_{sel['ts']}")
        if st.button("🖼️ Пересоздать SVG", key=f"graph_{sel['ts']}"):
            from target_config_graph import generate_target_config_svg
            generate_target_config_svg(tc_path, str(reports_dir / f"target_config_{sel['sn']}_{sel['ts']}.svg"))
            st.success("SVG создана")
            st.rerun()
    
    st.divider()
    st.subheader("📦 ZIP-пакет")
    
    zip_path = reports_dir / f"package_{sel['ts']}.zip"
    import zipfile
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for prefix, fpath in docs.items():
            p = Path(fpath)
            if p.exists():
                zf.write(p, p.name)
        if sa_path and Path(sa_path).exists():
            zf.write(sa_path, Path(sa_path).name)
        for pat in ["protocol_*.docx", "matrix_*.xlsx", "target_config_*.svg", "full_report_*.md", "full_report_*.pdf"]:
            for ff in sorted(reports_dir.glob(pat), key=lambda x: x.stat().st_mtime, reverse=True)[:1]:
                zf.write(ff, ff.name)
    
    with open(zip_path, "rb") as fh:
        st.download_button("📦 ZIP (все документы)", fh.read(), file_name=zip_path.name,
                         mime="application/zip", use_container_width=True, key=f"zip_{sel['ts']}")
    
    st.divider()
    with st.expander("🗑️ Управление"):
        total = len(list(reports_dir.glob("*")))
        size = sum(f.stat().st_size for f in reports_dir.glob("*") if f.is_file()) / 1024 / 1024
        st.write(f"Файлов: {total}, Размер: {size:.1f} MB")
