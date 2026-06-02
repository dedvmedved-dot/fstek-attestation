"""
Пакетный аудит: одна конфигурация ПАК × несколько классификаций.
Запуск: python batch_audit.py input_data.json classifications.json
"""
import sys, json, os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from system_audit import SystemAuditor

def run_batch_audit(config_path: str, classifications_path: str):
    # Загружаем конфигурацию ПАК
    with open(config_path, "r", encoding="utf-8") as f:
        pak_data = json.load(f)
    
    # Загружаем список классификаций
    with open(classifications_path, "r", encoding="utf-8") as f:
        classifications = json.load(f)
    
    auditor = SystemAuditor()
    
    print("=" * 60)
    print(f"🚀 ПАКЕТНЫЙ АУДИТ: {len(classifications)} классификаций")
    print(f"📦 Конфигурация: {pak_data.get('system_name', 'ПАК')}")
    print("=" * 60)
    
    batch_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_dir = Path("reports") / f"batch_{batch_ts}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    for i, cls in enumerate(classifications, 1):
        cls_name = cls.get("name", f"Классификация {i}")
        print(f"\n{'='*40}")
        print(f"📋 {i}/{len(classifications)}: {cls_name}")
        print(f"{'='*40}")
        
        # Создаём копию pak_data с новой классификацией
        pak_copy = json.loads(json.dumps(pak_data))
        pak_copy["classification"] = {
            k: v for k, v in cls.items() if k != "name"
        }
        
        # Запускаем системный аудит
        result = auditor.audit_system(pak_copy)
        
        # Сохраняем в подпапку
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in cls_name)
        cls_dir = batch_dir / f"{i:02d}_{safe_name}"
        cls_dir.mkdir(exist_ok=True)
        
        # Генерируем документы
        documents = auditor.generate_documents(result, str(cls_dir))
        
        # Сохраняем полный результат
        result_path = cls_dir / f"system_audit.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # Генерируем DOCX и XLSX
        try:
            from report_docx import FSTEKReportGenerator
            docx_path = cls_dir / f"protocol_{safe_name}.docx"
            FSTEKReportGenerator(str(result_path)).generate(str(docx_path))
            print(f"   📄 DOCX: {docx_path.name}")
        except Exception as e:
            print(f"   ⚠️ DOCX: {e}")
        
        try:
            from report_xlsx import FSTEKExcelGenerator
            xlsx_path = cls_dir / f"matrix_{safe_name}.xlsx"
            FSTEKExcelGenerator(str(result_path)).generate(str(xlsx_path))
            print(f"   📊 XLSX: {xlsx_path.name}")
        except Exception as e:
            print(f"   ⚠️ XLSX: {e}")
        
        # Генерируем Markdown и PDF
        try:
            from report_markdown import generate_full_report_md, generate_full_report_pdf
            md_path = cls_dir / f"report_{safe_name}.md"
            md_content = generate_full_report_md(str(result_path))
            md_path.write_text(md_content, encoding='utf-8')
            print(f"   📝 MD: {md_path.name}")
            
            pdf_path = cls_dir / f"report_{safe_name}.pdf"
            generate_full_report_pdf(str(result_path), str(pdf_path))
            print(f"   📄 PDF: {pdf_path.name}")
        except Exception as e:
            print(f"   ⚠️ MD/PDF: {e}")
        
        # Генерируем SVG схему
        try:
            from target_config_graph import generate_target_config_svg
            svg_path = cls_dir / f"target_config_{safe_name}.svg"
            tc_json = cls_dir / f"03_target_config_{safe_name}_*.json"
            tc_files = list(cls_dir.glob("03_target_config_*.json"))
            if tc_files:
                generate_target_config_svg(str(tc_files[0]), str(svg_path))
                print(f"   🖼️ SVG: {svg_path.name}")
        except Exception as e:
            print(f"   ⚠️ SVG: {e}")
        
        # Сводка
        oa = result.get("overall_assessment", {})
        summary = {
            "name": cls_name,
            "compliance_pct": oa.get("overall_compliance_pct", 0),
            "fully_compliant": oa.get("fully_compliant", 0),
            "partially_compliant": oa.get("partially_compliant", 0),
            "non_compliant": oa.get("non_compliant", 0),
            "total": oa.get("total_requirements", 0),
        }
        results.append(summary)
        
        print(f"\n   📊 Соответствие: {summary['compliance_pct']}%")
        print(f"   ✅ Полностью: {summary['fully_compliant']}")
        print(f"   ⚠️ Частично: {summary['partially_compliant']}")
        print(f"   ❌ Нет: {summary['non_compliant']}")
    
    # Итоговая сводка
    print(f"\n{'='*60}")
    print(f"📊 ИТОГОВАЯ СВОДКА")
    print(f"{'='*60}")
    print(f"{'Классификация':<35} {'Соотв.':<10} {'✅':<6} {'⚠️':<6} {'❌':<6}")
    print("-" * 65)
    for r in results:
        print(f"{r['name']:<35} {r['compliance_pct']}%{'':<5} {r['fully_compliant']:<6} {r['partially_compliant']:<6} {r['non_compliant']:<6}")
    
    # Сохраняем сводку
    summary_path = batch_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 Все результаты: {batch_dir}")
    print(f"📊 Сводка: {summary_path}")

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "input_data.json"
    classifications_path = sys.argv[2] if len(sys.argv) > 2 else "classifications.json"
    run_batch_audit(config_path, classifications_path)
