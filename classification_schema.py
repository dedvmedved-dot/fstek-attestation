"""
Многофакторная классификация системы.
Определяет применимые требования на основе всех параметров.
"""

from typing import List, Dict
from dataclasses import dataclass, field
from enum import Enum


class SystemType(Enum):
    GIS = "ГИС"
    ISPDN = "ИСПДн"
    KII = "КИИ"
    ASUTP = "АСУ ТП"
    STANDALONE = "Автономная"


class ThreatType(Enum):
    TYPE_1 = "1-й тип"  # НДВ в системном ПО
    TYPE_2 = "2-й тип"  # НДВ в прикладном ПО
    TYPE_3 = "3-й тип"  # Отсутствие НДВ


@dataclass
class ClassificationProfile:
    """Профиль классификации системы"""
    # Базовые параметры
    system_type: str                    # "ГИС", "ИСПДн", "КИИ"
    organization_type: str              # "государственное унитарное предприятие"
    
    # Класс по приказам ФСТЭК
    fstek_117_class: str = ""           # "К1", "К2", "К3"
    fstek_21_class: str = ""            # "1Г", "2Г", "3Г", "4Г"
    fstek_239_class: str = ""           # Для КИИ
    
    # ДСП
    has_dsp: bool = False               # Наличие документов ДСП
    
    # ИСПДн
    ispdn_category: str = ""            # "иные", "специальные", "биометрические"
    ispdn_subjects_count: int = 0
    ispdn_subjects_category: str = ""   # "<100000", ">100000"
    
    # Угрозы
    threat_type: str = ""               # "1-й тип", "2-й тип", "3-й тип"
    
    # Постановление №1119
    pp1119_level: str = ""              # "УЗ-1", "УЗ-2", "УЗ-3", "УЗ-4"
    
    def get_search_queries(self) -> List[str]:
        """Генерирует поисковые запросы для ChromaDB на основе всех параметров"""
        queries = []
        
        # Базовые запросы по типу системы
        if "ГИС" in self.system_type:
            queries.append(f"Требования к защите государственных информационных систем класс {self.fstek_117_class}")
            queries.append("Меры защиты информации для ГИС")
            queries.append("Состав мер защиты ГИС РСБ АУД ЗИС")
        
        if "ИСПДн" in self.system_type:
            queries.append(f"Требования к защите персональных данных {self.ispdn_category} категории")
            queries.append(f"Меры защиты ИСПДн уровень {self.pp1119_level}")
            queries.append(f"Защита персональных данных при количестве субъектов {self.ispdn_subjects_count}")
        
        if "КИИ" in self.system_type:
            queries.append(f"Требования к безопасности критической информационной инфраструктуры")
            queries.append("Меры защиты КИИ по приказу 239")
        
        # Запросы по наличию ДСП
        if self.has_dsp:
            queries.append("Требования к защите информации ДСП")
            queries.append("Меры защиты документов служебного пользования")
        
        # Запросы по типу угроз
        if self.threat_type:
            queries.append(f"Требования к защите информации при угрозах {self.threat_type}")
            queries.append("Меры защиты от недокументированных возможностей")
            if "3-й тип" in self.threat_type:
                queries.append("Требования к сертифицированным СЗИ отсутствие НДВ")
        
        # Запросы по ПП №1119
        if self.pp1119_level:
            queries.append(f"Требования к защите персональных данных уровень {self.pp1119_level}")
            queries.append(f"Меры защиты информации УЗ-4 базовый уровень")
        
        # Общие запросы
        queries.extend([
            "Требования к антивирусной защите",
            "Требования к разграничению доступа",
            "Требования к регистрации событий безопасности",
            "Требования к целостности программного обеспечения",
            "Требования к криптографической защите",
            "Требования к межсетевому экранированию",
            "Требования к обнаружению вторжений",
        ])
        
        return queries
    
    def get_description(self) -> str:
        """Текстовое описание профиля для LLM"""
        parts = []
        
        if self.system_type:
            parts.append(f"Тип системы: {self.system_type} ({self.organization_type})")
        
        if self.fstek_117_class:
            parts.append(f"Класс защищённости по приказу №117: {self.fstek_117_class}")
        
        if self.has_dsp:
            parts.append("В системе обрабатываются сведения ДСП")
        
        if self.ispdn_category:
            parts.append(f"Категория ПДн: {self.ispdn_category}")
            parts.append(f"Количество субъектов: {self.ispdn_subjects_count}")
        
        if self.threat_type:
            parts.append(f"Тип угроз: {self.threat_type}")
        
        if self.pp1119_level:
            parts.append(f"Уровень защищённости по ПП №1119: {self.pp1119_level}")
        
        return "\n".join(parts)


# ========== ПРИМЕР ИСПОЛЬЗОВАНИЯ ==========

def example_classification():
    """Пример классификации из вашего ТЗ"""
    profile = ClassificationProfile(
        system_type="ГИС государственного унитарного предприятия",
        organization_type="государственное унитарное предприятие",
        fstek_117_class="К2",
        has_dsp=True,
        ispdn_category="иные категории ПДн (ФИО, адрес, телефон)",
        ispdn_subjects_count=50000,
        threat_type="3-й тип (отсутствие недокументированных возможностей)",
        pp1119_level="УЗ-4",
    )
    
    print("📋 ПРОФИЛЬ КЛАССИФИКАЦИИ:")
    print(profile.get_description())
    print(f"\n🔍 СГЕНЕРИРОВАНО {len(profile.get_search_queries())} ПОИСКОВЫХ ЗАПРОСОВ:")
    for i, q in enumerate(profile.get_search_queries(), 1):
        print(f"  {i}. {q}")
    
    return profile


if __name__ == "__main__":
    example_classification()

# ========== ФИЛЬТР ПРИМЕНИМОСТИ ТРЕБОВАНИЙ ==========

# Ключевые слова в тексте требования → типы компонентов, к которым оно применимо
REQUIREMENT_COMPONENT_FILTER = {
    # Антивирусная защита
    "антивирус": ["ОС", "СЗИ", "Антивирус", "ВМ", "Приложение"],
    "вирус": ["ОС", "СЗИ", "Антивирус", "ВМ", "Приложение"],
    "АВЗ": ["ОС", "СЗИ", "Антивирус", "ВМ", "Приложение"],
    
    # Замкнутая программная среда
    "замкнут": ["ОС"],
    "ЗПС": ["ОС"],
    
    # Шифрование, криптография
    "шифрован": ["ОС", "СКЗИ", "Хранилище", "Сервер"],
    "крипто": ["ОС", "СКЗИ", "Хранилище", "Сервер"],
    "СКЗИ": ["СКЗИ", "ОС", "Сервер"],
    "LUKS": ["ОС", "Хранилище"],
    
    # Межсетевое экранирование
    "межсетев": ["ОС", "Сетевое оборудование", "Коммутатор"],
    "firewall": ["ОС", "Сетевое оборудование"],
    "iptables": ["ОС"],
    
    # Обнаружение вторжений
    "вторжен": ["СОВ", "IDS", "Сетевое оборудование", "ОС"],
    "IDS": ["СОВ", "IDS", "Сетевое оборудование"],
    "Suricata": ["СОВ", "IDS"],
    
    # Аудит, регистрация событий
    "аудит": ["ОС", "СЗИ НСД", "Приложение", "Мониторинг"],
    "audit": ["ОС", "СЗИ НСД"],
    "регистрац": ["ОС", "СЗИ НСД", "Приложение", "Мониторинг"],
    "журнал": ["ОС", "СЗИ НСД", "Приложение", "Мониторинг"],
    
    # Аутентификация, управление доступом
    "аутентифик": ["ОС", "FreeIPA", "LDAP", "Аутентификация", "Приложение"],
    "идентифик": ["ОС", "FreeIPA", "LDAP", "Аутентификация", "Приложение"],
    "доступ": ["ОС", "СЗИ НСД", "Приложение", "Сетевое оборудование"],
    "учетн": ["ОС", "FreeIPA", "LDAP", "Приложение"],
    
    # Целостность
    "целостн": ["ОС", "СЗИ НСД", "Хранилище", "Приложение"],
    "контроль целост": ["ОС", "СЗИ НСД", "Хранилище"],
    "AIDE": ["ОС"],
    "PARSEC": ["ОС", "СЗИ НСД"],
    
    # Репликация, отказоустойчивость
    "репликац": ["Хранилище", "DRBD", "Сервер"],
    "DRBD": ["Хранилище", "DRBD", "Сервер"],
    "отказоустой": ["Сервер", "Кластер", "Pacemaker"],
    "кластер": ["Кластер", "Pacemaker", "Corosync", "Сервер"],
    "Pacemaker": ["Кластер", "Pacemaker"],
    "Corosync": ["Кластер", "Corosync"],
    
    # Виртуализация
    "виртуал": ["Гипервизор", "KVM", "ВМ", "Сервер"],
    "KVM": ["Гипервизор", "KVM", "Сервер"],
    "миграци": ["Гипервизор", "KVM", "Сервер"],
    
    # Мониторинг
    "мониторинг": ["Мониторинг", "ОС", "Сервер"],
    "Prometheus": ["Мониторинг"],
    "Grafana": ["Мониторинг"],
    
    # Сеть
    "VLAN": ["Сетевое оборудование", "Коммутатор"],
    "коммутат": ["Сетевое оборудование", "Коммутатор"],
    "маршрутиз": ["Сетевое оборудование", "Коммутатор"],
    
    # ДСП
    "ДСП": ["ОС", "СЗИ НСД", "Приложение", "Сервер"],
    "служебн": ["ОС", "СЗИ НСД", "Приложение", "Сервер"],
    
    # Персональные данные
    "персональн": ["ОС", "СЗИ НСД", "Приложение", "ВМ"],
    "ПДн": ["ОС", "СЗИ НСД", "Приложение", "ВМ"],
    
    # Физическая защита
    "физическ": ["Сервер", "Серверная платформа", "Аппаратный"],
    "аппаратн": ["Сервер", "Серверная платформа", "Аппаратный"],
    "Витязь": ["Сервер", "Серверная платформа", "Аппаратный"],
    "доверен": ["Сервер", "Серверная платформа", "Аппаратный", "ОС"],
}


def is_requirement_applicable(requirement_text: str, component_type: str, 
                              component_name: str = "") -> bool:
    """
    Проверяет, применимо ли требование к данному типу компонента.
    
    Args:
        requirement_text: текст требования из НПА
        component_type: тип компонента (ОС, СКЗИ, Сервер, ...)
        component_name: название компонента
    
    Returns:
        True, если требование потенциально применимо к компоненту
    """
    text_lower = requirement_text.lower()
    type_lower = component_type.lower()
    name_lower = component_name.lower()
    
    # Проверяем по ключевым словам
    for keyword, applicable_types in REQUIREMENT_COMPONENT_FILTER.items():
        if keyword.lower() in text_lower:
            # Проверяем, подходит ли тип компонента
            for at in applicable_types:
                if at.lower() in type_lower or at.lower() in name_lower:
                    return True
    
    # Если ключевых слов не найдено — считаем требование общим (применимо ко всем)
    # Проверяем только базовые типы, к которым обычно всё применимо
    always_applicable = ["ОС", "Сервер", "Серверная платформа", "СЗИ НСД"]
    for aa in always_applicable:
        if aa.lower() in type_lower:
            return True
    
    # Для узкоспециализированных компонентов без совпадений — не применимо
    return False


def filter_requirements(requirements: list, components: list, 
                        verbose: bool = True) -> list:
    """
    Фильтрует требования, оставляя только применимые к каждому компоненту.
    
    Returns:
        Список кортежей (requirement, component) только для применимых комбинаций
    """
    filtered = []
    skipped = 0
    
    for req in requirements:
        for comp in components:
            if is_requirement_applicable(
                req.get("text", ""),
                comp.get("component_type", ""),
                comp.get("component_name", ""),
            ):
                filtered.append((req, comp))
            else:
                skipped += 1
    
    if verbose:
        total = len(requirements) * len(components)
        print(f"🔍 Фильтр: {len(filtered)}/{total} комбинаций ({skipped} пропущено)")
    
    return filtered
