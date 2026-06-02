"""Генератор Markdown и PDF для всех типов отчётов."""
import json
from pathlib import Path


def generate_matrix_md(json_path: str) -> str:
    with open(json_path) as f:
        data = json.load(f)
    
    ra = data.get("requirement_analysis", {})
    reqs = data.get("requirements", [])
    doc_map = {r.get("paragraph_id", ""): r.get("source_document", "") for r in reqs}
    
    md = "# Матрица требований\n\n"
    md += "| № | Документ | Пункт | Статус | Рекомендация |\n"
    md += "|---|----------|-------|--------|--------------|\n"
    
    for i, (rid, a) in enumerate(ra.items(), 1):
        if not isinstance(a, dict):
            continue
        src = doc_map.get(rid, "")
        st = a.get("status", "—")
        icon = {"COMPLIANT": "✅", "NON_COMPLIANT": "❌", "PARTIALLY_COMPLIANT": "⚠️"}.get(st, "")
        rec = (a.get("recommendation", "") or "")[:150]
        md += f"| {i} | {src} | {rid} | {icon} {st} | {rec} |\n"
    
    return md


def generate_gaps_md(json_path: str) -> str:
    with open(json_path) as f:
        data = json.load(f)
    
    gaps = data.get("gaps", [])
    md = f"# Ведомость несоответствий ({len(gaps)})\n\n"
    
    if gaps:
        md += "| № | Пункт | Статус | Недостаток | Рекомендация |\n"
        md += "|---|-------|--------|------------|--------------|\n"
        for i, g in enumerate(gaps, 1):
            md += f"| {i} | {g.get('requirement_id','')} | {g.get('status','')} | {(g.get('gap_description','') or '')[:150]} | {(g.get('recommendation','') or '')[:150]} |\n"
    else:
        md += "✅ Несоответствий нет.\n"
    
    return md


def generate_target_md(json_path: str) -> str:
    with open(json_path) as f:
        data = json.load(f)
    
    changes = data.get("changes", [])
    desc = data.get("description", "")
    md = f"# Целевая конфигурация\n\n{desc}\n\n"
    
    if changes:
        md += "| № | Приор. | Компонент | Изменение | Требование |\n"
        md += "|---|--------|-----------|-----------|------------|\n"
        for i, c in enumerate(changes, 1):
            p = c.get("priority", "—")
            icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(p, "")
            md += f"| {i} | {icon} {p} | {c.get('component','')} | {(c.get('change','') or '')[:150]} | {c.get('requirement','')} |\n"
    
    return md


def generate_test_md(json_path: str) -> str:
    with open(json_path) as f:
        data = json.load(f)
    
    scenarios = data.get("test_scenarios", [])
    md = f"# Программа испытаний ({len(scenarios)} сценариев)\n\n"
    
    for s in scenarios:
        md += f"## {s.get('scenario_id','')}: {s.get('description','')}\n\n"
        md += f"**Требование:** {s.get('requirement','')}\n\n"
        md += f"**Методика:** {s.get('method','')}\n\n"
        md += f"**Ожидаемый результат:** {s.get('expected_result','')}\n\n"
        md += f"**Инструменты:** {', '.join(s.get('tools',[]))}\n\n---\n\n"
    
    return md


def generate_conclusion_md(json_path: str) -> str:
    with open(json_path) as f:
        data = json.load(f)
    
    md = f"# Заключение\n\n"
    md += f"**Соответствие:** {data.get('compliance_pct', 0)}%\n\n"
    md += f"**Решение:** {data.get('conclusion', '—')}\n\n"
    md += f"{data.get('summary', '')}\n\n"
    
    critical = data.get("critical_gaps", [])
    if critical:
        md += "## Критические несоответствия\n\n"
        for g in critical:
            md += f"- {g}\n"
    
    return md


def generate_full_report_md(audit_json_path: str) -> str:
    """Единый Markdown из всех 5 файлов сессии."""
    sa_path = Path(audit_json_path)
    reports_dir = sa_path.parent  # Для batch это папка сессии, для single — reports/
    
    with open(sa_path) as f:
        data = json.load(f)
    
    system_name = data.get("system_name", "ПАК")
    classification = data.get("classification", {})
    ts = sa_path.stem.replace("system_audit_", "")
    
    # Ищем файлы в папке с system_audit.json
    search_dir = sa_path.parent
    matrix_f = list(search_dir.glob("01_matrix_*.json"))
    gaps_f = list(search_dir.glob("02_gaps_*.json"))
    target_f = list(search_dir.glob("03_target_config_*.json"))
    test_f = list(search_dir.glob("04_test_program_*.json"))
    conclusion_f = list(search_dir.glob("05_conclusion_*.json"))
    
    files = {
        "matrix": matrix_f[0] if matrix_f else None,
        "gaps": gaps_f[0] if gaps_f else None,
        "target": target_f[0] if target_f else None,
        "test": test_f[0] if test_f else None,
        "conclusion": conclusion_f[0] if conclusion_f else None,
    }
    
    md = f"# Пакет документов аттестации — {system_name}\n\n"
    md += f"Дата: {ts[:4]}.{ts[4:6]}.{ts[6:8]}\n\n---\n\n"
    
    if files["matrix"] is not None:
        md += generate_matrix_md(str(files["matrix"])) + "\n\n---\n\n"
    if files["gaps"] is not None:
        md += generate_gaps_md(str(files["gaps"])) + "\n\n---\n\n"
    if files["target"] is not None:
        md += generate_target_md(str(files["target"])) + "\n\n---\n\n"
    if files["test"] is not None:
        md += generate_test_md(str(files["test"])) + "\n\n---\n\n"
    if files["conclusion"] is not None:
        md += generate_conclusion_md(str(files["conclusion"]))
    
    return md


def generate_full_report_pdf(audit_json_path: str, output_path: str = None) -> str:
    try:
        import markdown
        from weasyprint import HTML
    except ImportError:
        return ""
    
    md = generate_full_report_md(audit_json_path)
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{{font-family:'Times New Roman',serif;font-size:11pt;margin:1.5cm;}}
table{{border-collapse:collapse;width:100%;margin:8px 0;}}th,td{{border:1px solid #333;padding:5px;font-size:9pt;}}
th{{background-color:#4472C4;color:white;}}h1{{font-size:16pt;}}h2{{font-size:13pt;}}</style></head>
<body>{markdown.markdown(md, extensions=['tables'])}</body></html>"""
    
    if output_path is None:
        output_path = str(Path(audit_json_path).with_suffix('.pdf'))
    HTML(string=html).write_pdf(output_path)
    print(f"📄 PDF: {output_path}")
    return output_path
