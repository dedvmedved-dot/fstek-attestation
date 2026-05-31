"""
Генератор Graphviz-схемы целевой конфигурации ПАК.
"""

import json
from pathlib import Path
from datetime import datetime


def generate_target_config_dot(audit_json_path: str) -> str:
    with open(audit_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    system_name = data.get("system_name", "ПАК")
    classification = data.get("classification", {})
    
    if "changes" in data:
        target_config = data
    else:
        target_config = data.get("target_configuration", {})
    
    changes = target_config.get("changes", target_config.get("changes_required", []))
    description = target_config.get("description", "")
    verification = target_config.get("verification_method", "")
    
    short_desc = description[:120] + "..." if len(description) > 120 else description
    
    # Собираем классификацию в компактную строку
    class_lines = [
        f"Тип: {classification.get('system_type', '—')}",
        f"Класс (приказ №117): {classification.get('fstek_117_class', '—')}",
        f"Класс (приказ №21): {classification.get('fstek_21_class', '—')}",
        f"Уровень ПДн (ПП №1119): {classification.get('pp1119_level', '—')}",
        f"Тип угроз: {classification.get('threat_type', '—')}",
        f"Субъектов ПДн: {classification.get('ispdn_subjects_count', '—')}",
        f"ДСП: {'Да' if classification.get('has_dsp') else 'Нет'}",
    ]
    class_text = "\\n".join(class_lines)
    
    dot = f'''digraph TargetConfiguration {{
    rankdir=TB;
    splines=ortho;
    nodesep=0.5;
    ranksep=0.6;
    bgcolor="white";
    fontname="Arial";
    fontsize=18;
    label="ЦЕЛЕВАЯ КОНФИГУРАЦИЯ ПАК\\n{system_name}\\n{short_desc}";
    labelloc="t";
    fontcolor="black";
    
    node [shape=box, style="filled,rounded", fontname="Arial", fontsize=10, fontcolor="black", penwidth=1.5];
    
    // Классификация — правый верхний угол
    subgraph cluster_classification {{
        label="КЛАССИФИКАЦИЯ СИСТЕМЫ";
        style="filled";
        fillcolor="#E3F2FD";
        color="#1565C0";
        penwidth=2;
        fontname="Arial";
        fontsize=12;
        fontcolor="black";
        
        class_node [label="{class_text}", fillcolor="#BBDEFB", width=4.5];
    }}
    
    // Целевая конфигурация
    subgraph cluster_target {{
        label="ЦЕЛЕВАЯ КОНФИГУРАЦИЯ (100% СООТВЕТСТВИЕ)";
        style="filled";
        fillcolor="#E8F5E9";
        color="#2E7D32";
        penwidth=2;
        fontname="Arial";
        fontsize=12;
        fontcolor="black";
'''
    
    high = [c for c in changes if c.get("priority") == "HIGH"]
    medium = [c for c in changes if c.get("priority") == "MEDIUM"]
    low = [c for c in changes if c.get("priority") == "LOW"]
    
    change_id = 0
    
    for priority, items, color, fillcolor, label in [
        ("HIGH", high, "#C62828", "#FFCDD2", "КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ (HIGH)"),
        ("MEDIUM", medium, "#E65100", "#FFE0B2", "РЕКОМЕНДУЕМЫЕ ИЗМЕНЕНИЯ (MEDIUM)"),
        ("LOW", low, "#2E7D32", "#C8E6C9", "ОПТИМИЗАЦИЯ (LOW)"),
    ]:
        if items:
            dot += f'''
        subgraph cluster_{priority.lower()} {{
            label="{label}";
            style="filled";
            fillcolor="{fillcolor}";
            color="{color}";
            penwidth=2;
            fontname="Arial";
            fontsize=11;
            fontcolor="black";
'''
            for item in items:
                change_id += 1
                component = item.get("component", "")
                change = item.get("change", "")
                requirement = item.get("requirement", "")
                short_change = change[:120] + "..." if len(change) > 120 else change
                
                dot += f'''
            change_{change_id} [label="ИЗМЕНЕНИЕ {change_id}\\nКомпонент: {component}\\n{short_change}\\nТребование: {requirement}", fillcolor="white"];
'''
            dot += '''
        }
'''
    
    if verification:
        short_ver = verification[:150] + "..." if len(verification) > 150 else verification
        dot += f'''
        subgraph cluster_verification {{
            label="МЕТОД ПРОВЕРКИ";
            style="filled";
            fillcolor="#F3E5F5";
            color="#6A1B9A";
            penwidth=2;
            fontname="Arial";
            fontsize=11;
            fontcolor="black";
            
            verify [label="{short_ver}", fillcolor="#E1BEE7"];
        }}
'''
    
    # Связи между изменениями
    dot += '''
    }
    
    class_node -> change_1 [style="invis"];
'''
    
    dot += '''
}
'''
    
    return dot


def generate_target_config_svg(audit_json_path: str, output_path: str = None) -> str:
    import subprocess
    import tempfile
    
    dot_content = generate_target_config_dot(audit_json_path)
    
    with tempfile.NamedTemporaryFile(suffix='.dot', delete=False, mode='w', encoding='utf-8') as f:
        f.write(dot_content)
        dot_path = f.name
    
    if output_path is None:
        output_path = dot_path.replace('.dot', '.svg')
    
    try:
        subprocess.run(['dot', '-Tsvg', dot_path, '-o', output_path], check=True)
        print(f"🖼️ SVG сохранена: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка: {e}")
    finally:
        Path(dot_path).unlink(missing_ok=True)
    
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        files = sorted(Path("reports").glob("03_target_config_*.json"), reverse=True)
        json_path = str(files[0]) if files else None
    
    if json_path:
        # Имя файла по названию системы
        with open(json_path) as f:
            data = json.load(f)
        system_name = data.get("system_name", "ПАК")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path("reports") / f"target_config_{system_name}_{ts}.svg"
        generate_target_config_svg(json_path, str(output))
