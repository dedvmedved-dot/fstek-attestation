#!/usr/bin/env python3
"""
Проверка окружения системы аттестации ФСТЭК.
Запуск: python check_env.py
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def check_python():
    print(f"🐍 Python: {sys.version}")
    assert sys.version_info >= (3, 11), "Требуется Python 3.11+"

def check_dotenv():
    env_path = Path(".env")
    if env_path.exists():
        print("✅ .env файл найден")
    else:
        print("❌ .env файл не найден. Скопируйте .env.example в .env")
        sys.exit(1)

def check_npa_pdfs():
    npa_dir = os.getenv("NPA_PDF_DIR", "")
    if not npa_dir:
        print("⚠️  NPA_PDF_DIR не задан в .env")
        return
    
    path = Path(npa_dir)
    if not path.exists():
        print(f"❌ Папка {npa_dir} не существует")
        return
    
    pdfs = list(path.glob("*.pdf"))
    if pdfs:
        print(f"✅ Найдено {len(pdfs)} PDF-файлов:")
        for pdf in pdfs:
            size_mb = pdf.stat().st_size / (1024 * 1024)
            print(f"   - {pdf.name} ({size_mb:.1f} MB)")
    else:
        print(f"⚠️  В папке {npa_dir} нет PDF-файлов")

def check_docker():
    try:
        result = subprocess.run(["docker", "ps"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Docker работает")
        else:
            print("❌ Docker не доступен")
    except FileNotFoundError:
        print("❌ Docker не установлен")

def check_docker_containers():
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"],
            capture_output=True, text=True
        )
        containers = result.stdout.strip().split("\n")
        fstek_containers = [c for c in containers if "fstek" in c]
        if fstek_containers:
            print(f"✅ Контейнеры ФСТЭК запущены: {len(fstek_containers)}")
        else:
            print("⚠️  Контейнеры ФСТЭК не запущены (make infra)")
    except:
        pass

def check_llm_access():
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if api_key and api_key != "sk-your-api-key-here":
            print("✅ DEEPSEEK_API_KEY задан")
        else:
            print("⚠️  DEEPSEEK_API_KEY не задан или используется значение по умолчанию")
    elif provider == "local":
        url = os.getenv("LLAMA_SERVER_URL", "")
        print(f"🔍 Проверка llama.cpp: {url}")
        try:
            import requests
            resp = requests.get(f"{url.replace('/v1', '')}/health", timeout=5)
            if resp.status_code == 200:
                print("✅ llama-server доступен")
            else:
                print("⚠️  llama-server ответил с ошибкой")
        except:
            print("❌ llama-server не доступен")

def check_wsl_gpu():
    """Проверка доступности GPU в WSL2"""
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if "RTX 5080" in result.stdout or "5080" in result.stdout:
            print("✅ GPU NVIDIA доступна в WSL2")
        elif result.returncode == 0:
            print("✅ GPU NVIDIA доступна (модель не определена)")
        else:
            print("⚠️  nvidia-smi не сработал")
    except FileNotFoundError:
        print("⚠️  nvidia-smi не найден (CUDA не установлена в WSL2?)")

def check_ports():
    """Проверка занятости портов"""
    import socket
    
    ports = {
        5433: "PostgreSQL",
        8001: "ChromaDB",
        6380: "Redis",
        8501: "Streamlit",
    }
    
    for port, service in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        if result == 0:
            print(f"⚠️  Порт {port} ({service}) занят")
        else:
            print(f"✅ Порт {port} ({service}) свободен")

def main():
    print("=" * 60)
    print("🔍 ПРОВЕРКА ОКРУЖЕНИЯ СИСТЕМЫ АТТЕСТАЦИИ ФСТЭК")
    print("=" * 60)
    
    checks = [
        ("Python", check_python),
        (".env файл", check_dotenv),
        ("WSL2 GPU", check_wsl_gpu),
        ("Порты", check_ports),
        ("Docker", check_docker),
        ("Контейнеры", check_docker_containers),
        ("PDF НПА", check_npa_pdfs),
        ("LLM доступ", check_llm_access),
    ]
    
    for name, func in checks:
        try:
            func()
        except Exception as e:
            print(f"❌ {name}: {e}")
    
    print("\n" + "=" * 60)
    print("Готово! Исправьте ошибки и запускайте 'make infra'")
    print("=" * 60)

if __name__ == "__main__":
    main()
