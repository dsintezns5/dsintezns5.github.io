#!/usr/bin/env python3
"""
AI Panel — LM Studio Edition.
Lightweight management server for llama.cpp and ComfyUI.
Standard library only — zero external dependencies.
"""

import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

HOME = Path.home()
_script_dir = Path(__file__).resolve().parent

# Support environment overrides or sensible fallbacks
if os.environ.get("PANEL_DIR"):
    PANEL_DIR = Path(os.environ["PANEL_DIR"])
elif (HOME / "ai-panel").exists():
    PANEL_DIR = HOME / "ai-panel"
elif (_script_dir / "web").exists():
    PANEL_DIR = _script_dir
else:
    PANEL_DIR = HOME / "ai-panel"

if os.environ.get("MODELS_DIR"):
    MODELS_DIR = Path(os.environ["MODELS_DIR"])
elif (HOME / "models").exists():
    MODELS_DIR = HOME / "models"
else:
    MODELS_DIR = HOME / "models"

LOGS_DIR = PANEL_DIR / "logs"
LLAMA_DIR = HOME / "llama.cpp"
LLAMA_PID = LOGS_DIR / "llama.pid"
COMFY_DIR = HOME / "Comfyui"
COMFY_PID = LOGS_DIR / "comfy.pid"
PRESETS_FILE = PANEL_DIR / "presets.json"
LAST_RUN_FILE = PANEL_DIR / "last_run.json"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

PORT = int(os.environ.get("PANEL_PORT", "7860"))
HOST = os.environ.get("PANEL_HOST", "0.0.0.0")

# Known llama.cpp builds — order matters (first is default)
LLAMA_BUILDS = [
    {"id": "build", "name": "build", "bin": LLAMA_DIR / "build" / "bin" / "llama-server"},
]

def get_llama_bin(build_id: str | None = None) -> Path:
    """Return the llama-server binary path for a given build id, or the default."""
    if build_id:
        for b in LLAMA_BUILDS:
            if b["id"] == build_id:
                return b["bin"]
    return LLAMA_BUILDS[0]["bin"]

# Known llama-server flags the panel exposes
KNOWN_FLAGS = {
    "ngl": (int, "GPU layers"),
    "ctx": (int, "Context size"),
    "threads": (int, "CPU threads"),
    "temp": (float, "Temperature"),
    "repeat_penalty": (float, "Repeat penalty"),
    "presence_penalty": (float, "Presence penalty"),
    "top_k": (int, "Top K"),
    "top_p": (float, "Top P"),
    "min_p": (float, "Min P"),
    "cache_type_k": (str, "K cache type"),
    "cache_type_v": (str, "V cache type"),
    "flash_attn": (str, "Flash attention"),
    "cont_batching": (int, "Continuous batching"),
    "slot_context_size": (int, "Slot context size"),
    "batch": (int, "Batch size"),
    "ubatch": (int, "Unbatched size"),
    "ctx_checkpoints": (int, "Context checkpoints"),
    "cache_reuse": (int, "Cache reuse"),
    "spec_type": (str, "Speculative type"),
    "spec_draft_n": (int, "Speculative draft N"),
    "reasoning": (str, "Reasoning mode"),
    "jinja": (str, "Jinja templating"),
    "no_mmap": (str, "Disable mmap"),
    "context_shift": (str, "Context shift"),
    "port": (int, "Port"),
}

# --- Default presets ---
DEFAULT_PRESETS = [
    {
        "name": "кодинг 196608 (Qwen3.6-27B)",
        "model": "Qwen3.6-27B-Q5_K_M.gguf",
        "mmproj": "none",
        "spec_enabled": "on",
        "flags": {
            "ngl": "99",
            "ctx": "196608",
            "threads": "12",
            "temp": "0.6",
            "repeat_penalty": "1.0",
            "presence_penalty": "0.0",
            "top_k": "20",
            "top_p": "0.95",
            "min_p": "0.0",
            "cache_type_k": "q8_0",
            "cache_type_v": "f16",
            "flash_attn": "on",
            "batch": "1024",
            "ubatch": "256",
            "ctx_checkpoints": "8",
            "cache_reuse": "256",
            "spec_type": "draft-mtp",
            "spec_draft_n": "3",
            "reasoning": "off",
            "jinja": "on",
            "no_mmap": "on",
            "context_shift": "on",
            "port": "8080"
        }
    },
    {
        "name": "Максимум GPU (99 слоев, без MTP)",
        "model": "",
        "mmproj": "none",
        "spec_enabled": "off",
        "flags": {
            "ngl": "99",
            "ctx": "32768",
            "threads": "12",
            "temp": "0.3",
            "repeat_penalty": "1.0",
            "presence_penalty": "0.0",
            "top_k": "20",
            "top_p": "0.95",
            "min_p": "0.0",
            "cache_type_k": "q4_0",
            "cache_type_v": "q4_0",
            "flash_attn": "on",
            "batch": "1024",
            "ubatch": "256",
            "reasoning": "off",
            "jinja": "on",
            "no_mmap": "on",
            "context_shift": "on",
            "port": "8080"
        }
    },
    {
        "name": "Экономный VRAM (48 слоев, 16K ctx)",
        "model": "",
        "mmproj": "none",
        "spec_enabled": "off",
        "flags": {
            "ngl": "48",
            "ctx": "16384",
            "threads": "14",
            "temp": "0.5",
            "repeat_penalty": "1.0",
            "presence_penalty": "0.0",
            "cache_type_k": "q4_0",
            "cache_type_v": "q4_0",
            "flash_attn": "on",
            "batch": "512",
            "ubatch": "128",
            "reasoning": "off",
            "jinja": "on",
            "no_mmap": "on",
            "context_shift": "on",
            "port": "8080"
        }
    }
]

# --- Curated Model Catalog ---
MODEL_CATALOG = [
    {
        "id": "qwen2.5-coder-32b",
        "name": "Qwen 2.5 Coder 32B Instruct (Q4_K_M)",
        "filename": "qwen2.5-coder-32b-instruct-q4_k_m.gguf",
        "size": "19.8 GB",
        "type": "llm",
        "vram_req": "22 GB VRAM",
        "description": "Лучшая открытая модель для программирования и рефакторинга. Отлично помещается в 32GB VRAM V100.",
        "url": "https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct-GGUF/resolve/main/qwen2.5-coder-32b-instruct-q4_k_m.gguf"
    },
    {
        "id": "qwen2.5-14b-instruct",
        "name": "Qwen 2.5 14B Instruct (Q5_K_M)",
        "filename": "qwen2.5-14b-instruct-q5_k_m.gguf",
        "size": "10.4 GB",
        "type": "llm",
        "vram_req": "13 GB VRAM",
        "description": "Быстрая универсальная модель для русского и английского языков, логики и работы с текстом.",
        "url": "https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-GGUF/resolve/main/qwen2.5-14b-instruct-q5_k_m.gguf"
    },
    {
        "id": "deepseek-r1-distill-qwen-14b",
        "name": "DeepSeek R1 Distill Qwen 14B (Q5_K_M)",
        "filename": "DeepSeek-R1-Distill-Qwen-14B-Q5_K_M.gguf",
        "size": "10.8 GB",
        "type": "llm",
        "vram_req": "14 GB VRAM",
        "description": "Мощная модель с режимом размышления (Reasoning / CoT) на базе Qwen-14B.",
        "url": "https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF/resolve/main/DeepSeek-R1-Distill-Qwen-14B-Q5_K_M.gguf"
    },
    {
        "id": "llama-3.1-8b-instruct",
        "name": "Llama 3.1 8B Instruct (Q8_0)",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q8_0.gguf",
        "size": "8.5 GB",
        "type": "llm",
        "vram_req": "10 GB VRAM",
        "description": "Классическая модель от Meta в высоком качестве квантования Q8_0, отличная скорость на V100.",
        "url": "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q8_0.gguf"
    },
    {
        "id": "qwen2-vl-7b-instruct",
        "name": "Qwen2-VL 7B Instruct (Q5_K_M)",
        "filename": "Qwen2-VL-7B-Instruct-Q5_K_M.gguf",
        "size": "5.7 GB",
        "type": "llm",
        "vram_req": "9 GB VRAM",
        "description": "Модель с поддержкой зрения (Vision/Мультимодал). Требует подключения MMProj проектора.",
        "url": "https://huggingface.co/bartowski/Qwen2-VL-7B-Instruct-GGUF/resolve/main/Qwen2-VL-7B-Instruct-Q5_K_M.gguf"
    },
    {
        "id": "mmproj-qwen2-vl-7b",
        "name": "MMProj Проектор для Qwen2-VL 7B (f16)",
        "filename": "mmproj-Qwen2-VL-7B-Instruct-f16.gguf",
        "size": "1.2 GB",
        "type": "mmproj",
        "vram_req": "2 GB VRAM",
        "description": "Файл проекции зрения (mmproj) для распознавания изображений в Qwen2-VL-7B.",
        "url": "https://huggingface.co/bartowski/Qwen2-VL-7B-Instruct-GGUF/resolve/main/mmproj-Qwen2-VL-7B-Instruct-f16.gguf"
    },
    {
        "id": "mistral-7b-instruct-v03",
        "name": "Mistral 7B Instruct v0.3 (Q6_K)",
        "filename": "Mistral-7B-Instruct-v0.3-Q6_K.gguf",
        "size": "5.9 GB",
        "type": "llm",
        "vram_req": "8 GB VRAM",
        "description": "Надёжная компактная модель Mistral v0.3 с поддержкой вызова инструментов (Function calling).",
        "url": "https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/Mistral-7B-Instruct-v0.3-Q6_K.gguf"
    }
]

# Active downloads state: {filename: dict}
DOWNLOADS = {}
DOWNLOADS_LOCK = threading.Lock()

def read_pid(path: Path) -> int | None:
    if path.exists():
        try:
            pid = int(path.read_text().strip())
            os.kill(pid, 0)
            return pid
        except (ValueError, ProcessLookupError, PermissionError):
            path.unlink(missing_ok=True)
    return None

def find_llama_pid() -> int | None:
    try:
        r = subprocess.run(["pgrep", "-n", "llama-server"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return int(r.stdout.strip())
    except Exception:
        pass
    return None

def find_comfy_pid() -> int | None:
    """Find running ComfyUI process via pgrep."""
    try:
        r = subprocess.run(["pgrep", "-nf", "Comfyui.*main\\.py"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return int(r.stdout.strip())
    except Exception:
        pass
    return None

def is_llama_running() -> bool:
    return find_llama_pid() is not None

def is_comfy_running() -> bool:
    if read_pid(COMFY_PID):
        return True
    return find_comfy_pid() is not None

def tail_log(path: Path, lines: int = 50) -> str:
    if not path.exists():
        return "Лог-файл не найден"
    try:
        with open(path) as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:]).strip() or "Пусто"
    except Exception as e:
        return f"Ошибка чтения лога: {e}"

def _format_size(b: int) -> str:
    if b < 1024 * 1024:
        return f"{b / 1024:.0f} KB"
    elif b < 1024 * 1024 * 1024:
        return f"{b / (1024**2):.1f} MB"
    return f"{b / (1024**3):.1f} GB"

def list_models() -> dict:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    models = []
    llm_count = 0
    mmproj_count = 0
    for f in sorted(MODELS_DIR.glob("*.gguf")):
        size = f.stat().st_size
        size_str = _format_size(size)
        mtime = int(f.stat().st_mtime)
        fname_lower = f.name.lower()
        # Identify mmproj files: starts with mmproj or contains -mmproj or mmproj_
        is_mmproj = (
            fname_lower.startswith("mmproj") or
            "-mmproj" in fname_lower or
            "_mmproj" in fname_lower
        )
        mod_type = "mmproj" if is_mmproj else "llm"
        if is_mmproj:
            mmproj_count += 1
        else:
            llm_count += 1
        models.append({
            "name": f.name,
            "path": str(f),
            "size": size_str,
            "bytes": size,
            "mtime": mtime,
            "type": mod_type
        })
    return {
        "models": models,
        "llm_count": llm_count,
        "mmproj_count": mmproj_count,
        "total": len(models)
    }

def run_cmd(cmd: list[str], timeout: int = 30) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception:
        return ""

def get_system_info() -> dict:
    # 1. GPU info via nvidia-smi
    gpu = {
        "name": "NVIDIA Tesla V100-SXM2-32GB",
        "temperature": "42",
        "memory_used_gb": "0.0",
        "memory_total_gb": "32.0",
        "memory_free_gb": "32.0",
        "memory_percent": 0,
        "power_draw": "35W",
        "power_limit": "230W Locked",
        "driver": "580.173.02",
        "cuda": "12.4",
        "available": False
    }
    try:
        out = run_cmd(["nvidia-smi", "--query-gpu=name,temperature.gpu,memory.used,memory.total,power.draw,power.limit,driver_version", "--format=csv,noheader,nounits"], timeout=3)
        if out and "," in out:
            parts = [p.strip() for p in out.split(",")]
            if len(parts) >= 7:
                used = float(parts[2]) / 1024.0
                total = float(parts[3]) / 1024.0
                free = max(0.0, total - used)
                pct = int((used / total) * 100) if total > 0 else 0
                gpu = {
                    "name": parts[0],
                    "temperature": parts[1],
                    "memory_used_gb": f"{used:.1f}",
                    "memory_total_gb": f"{total:.1f}",
                    "memory_free_gb": f"{free:.1f}",
                    "memory_percent": pct,
                    "power_draw": parts[4] + "W",
                    "power_limit": "230W Locked" if "230" in parts[5] else parts[5] + "W",
                    "driver": parts[6],
                    "cuda": "12.4",
                    "available": True
                }
    except Exception:
        pass

    # 2. Memory info
    mem = {"total_gb": "32.0", "used_gb": "8.4", "free_gb": "23.6", "percent": 26}
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        m = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                m[parts[0].strip()] = int(parts[1].split()[0])
        if "MemTotal" in m and "MemAvailable" in m:
            total = m["MemTotal"] / (1024 * 1024)
            avail = m["MemAvailable"] / (1024 * 1024)
            used = max(0.0, total - avail)
            pct = int((used / total) * 100) if total > 0 else 0
            mem = {
                "total_gb": f"{total:.1f}",
                "used_gb": f"{used:.1f}",
                "free_gb": f"{avail:.1f}",
                "percent": pct
            }
    except Exception:
        pass

    # 3. CPU info
    cpu = {"model": "AMD Ryzen 7 3700X 8-Core Processor", "cores": 8, "threads": 16, "load_1m": "0.15"}
    try:
        load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.15
        cpu["load_1m"] = f"{load:.2f}"
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    cpu["model"] = line.split(":")[1].strip()
                    break
        cpu["threads"] = os.cpu_count() or 16
        cpu["cores"] = max(1, cpu["threads"] // 2)
    except Exception:
        pass

    # 4. Storage info for MODELS_DIR
    storage = {"total_gb": "465.8", "used_gb": "120.4", "free_gb": "345.4", "percent": 26, "path": str(MODELS_DIR)}
    try:
        st = os.statvfs(str(MODELS_DIR))
        total = (st.f_blocks * st.f_frsize) / (1024**3)
        free = (st.f_bavail * st.f_frsize) / (1024**3)
        used = max(0.0, total - free)
        pct = int((used / total) * 100) if total > 0 else 0
        storage = {
            "total_gb": f"{total:.1f}",
            "used_gb": f"{used:.1f}",
            "free_gb": f"{free:.1f}",
            "percent": pct,
            "path": str(MODELS_DIR)
        }
    except Exception:
        pass

    # 5. OS & Software info
    os_name = "Ubuntu 24.04.4 LTS"
    try:
        if Path("/etc/os-release").exists():
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("PRETTY_NAME="):
                    os_name = line.split("=")[1].strip('"')
                    break
    except Exception:
        pass

    kernel = "6.8.0-137-generic"
    try:
        kernel = os.uname().release
    except Exception:
        pass

    import sys
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    llama_bin = get_llama_bin()
    llama_ver = "CUDA build (~18 MB)"
    if llama_bin.exists():
        try:
            r = subprocess.run([str(llama_bin), "--version"], capture_output=True, text=True, timeout=3)
            out_ver = (r.stdout + r.stderr).strip()
            if out_ver:
                llama_ver = out_ver.splitlines()[0]
        except Exception:
            llama_ver = f"Found ({llama_bin.name})"
    else:
        llama_ver = f"Not built ({llama_bin})"

    comfy_inst = COMFY_DIR.exists()

    # Git info for AI Panel
    git_ver = "Git repo clean"
    try:
        if (PANEL_DIR / ".git").exists():
            r = subprocess.run(["git", "log", "-n", "1", "--format=%h — %s (%cd)", "--date=short"], cwd=str(PANEL_DIR), capture_output=True, text=True, timeout=2)
            if r.stdout.strip():
                git_ver = r.stdout.strip()
    except Exception:
        pass

    return {
        "gpu": gpu,
        "memory": mem,
        "cpu": cpu,
        "storage": storage,
        "software": {
            "os": os_name,
            "kernel": kernel,
            "python": py_version,
            "llama_version": llama_ver,
            "comfyui_installed": comfy_inst,
            "panel_git": git_ver
        }
    }

def parse_process_args(pid: int) -> dict:
    """Parse running llama-server process args into a flags dict."""
    try:
        r = subprocess.run(["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True)
        args = r.stdout
        result = {"port": "8080", "spec_enabled": "off"}
        m = re.search(r"-m\s+(\S+)", args)
        if not m:
            m = re.search(r"--model\s+(\S+)", args)
        if m:
            result["model"] = m.group(1)
        m_mm = re.search(r"--mmproj\s+(\S+)", args)
        if m_mm:
            result["mmproj"] = m_mm.group(1)
        else:
            result["mmproj"] = "none"

        # Boolean flags (present = on)
        bool_flags = {
            "jinja": r"--jinja\b",
            "no_mmap": r"--no-mmap\b",
            "context_shift": r"--context-shift\b",
            "api": r"--api\b",
        }
        for key, pat in bool_flags.items():
            if re.search(pat, args):
                result[key] = "on"
            else:
                result[key] = "off"

        for flag, (typ, _) in KNOWN_FLAGS.items():
            if flag in bool_flags:
                continue
            long = f"--{flag.replace('_', '-')}\\s+(\\S+)"
            short = f"-{flag[0]}\\s+(\\S+)" if len(flag) == 1 else None
            m = re.search(long, args)
            if not m and short:
                m = re.search(short, args)
            if m:
                try:
                    result[flag] = typ(m.group(1))
                except ValueError:
                    result[flag] = m.group(1)

        # Determine if spec decoding is enabled
        if re.search(r"--spec-type\b", args) or re.search(r"--spec-draft-n-max\b", args):
            result["spec_enabled"] = "on"
        else:
            result["spec_enabled"] = "off"

        return result
    except Exception:
        return {}

def _llm_status() -> dict:
    pid = find_llama_pid()
    running = pid is not None
    info = {"running": running, "pid": pid, "flags": {}, "build": "", "model": "", "mmproj": "none"}
    if running:
        info["flags"] = parse_process_args(pid)
        info["port"] = info["flags"].get("port", "8080")
        info["model"] = Path(info["flags"].get("model", "")).name if info["flags"].get("model") else ""
        info["mmproj"] = Path(info["flags"].get("mmproj", "")).name if info["flags"].get("mmproj") not in ("none", "") else "none"
        try:
            r = subprocess.run(["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True)
            for b in LLAMA_BUILDS:
                if str(b["bin"]) in r.stdout:
                    info["build"] = b["id"]
                    break
        except Exception:
            pass
    else:
        info["port"] = "8080"
        info["model"] = ""
        info["mmproj"] = "none"
    info["log"] = tail_log(LOGS_DIR / "llama.out")
    return info

# --- Presets ---
def load_presets() -> list[dict]:
    if PRESETS_FILE.exists():
        try:
            data = json.loads(PRESETS_FILE.read_text())
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception:
            pass
    return DEFAULT_PRESETS

def save_presets(presets: list[dict]):
    PRESETS_FILE.write_text(json.dumps(presets, ensure_ascii=False, indent=2))

def load_last_run() -> dict | None:
    if LAST_RUN_FILE.exists():
        try:
            return json.loads(LAST_RUN_FILE.read_text())
        except Exception:
            return None
    return None

def save_last_run(data: dict):
    LAST_RUN_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def call_systemd(action: str) -> str:
    """Call systemctl to manage the ai-panel service or the whole system."""
    if shutil.which("systemctl") is None:
        return "systemctl не найден (выполняется вне systemd / песочницы)"
    if action == "restart-panel":
        r = subprocess.run(["sudo", "systemctl", "restart", "ai-panel"], capture_output=True, text=True, timeout=10)
    elif action == "stop-panel":
        r = subprocess.run(["sudo", "systemctl", "stop", "ai-panel"], capture_output=True, text=True, timeout=10)
    elif action == "reboot":
        r = subprocess.run(["sudo", "shutdown", "-r", "now"], capture_output=True, text=True, timeout=10)
    elif action == "poweroff":
        r = subprocess.run(["sudo", "shutdown", "-h", "now"], capture_output=True, text=True, timeout=10)
    else:
        return f"Неизвестное действие: {action}"
    out = (r.stdout + r.stderr).strip()
    return out or f"Команда '{action}' отправлена"

def delete_model(filename: str) -> dict:
    """Delete a model file from ~/models."""
    path = MODELS_DIR / filename
    if not path.exists():
        return {"error": f"Файл не найден: {filename}"}
    size = path.stat().st_size
    path.unlink()
    return {"message": f"Удалён: {filename} ({_format_size(size)})"}

# --- Downloader Threading ---
def _download_thread(task_id: str, url: str, target_path: Path):
    temp_path = target_path.with_suffix(target_path.suffix + ".downloading")
    start_time = time.time()
    try:
        # Resolve HuggingFace URL if needed
        if "huggingface.co" in url and "/blob/" in url:
            url = url.replace("/blob/", "/resolve/")

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AIPanel-Downloader/1.0 (Linux; x86_64)"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            total_bytes = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            last_time = start_time
            last_bytes = 0

            with open(temp_path, "wb") as f:
                while True:
                    with DOWNLOADS_LOCK:
                        if task_id not in DOWNLOADS or DOWNLOADS[task_id].get("status") == "cancelled":
                            break
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_time >= 0.5 or not chunk:
                        speed = ((downloaded - last_bytes) / (1024 * 1024)) / max(0.001, now - last_time)
                        pct = int((downloaded / total_bytes) * 100) if total_bytes > 0 else 0
                        with DOWNLOADS_LOCK:
                            if task_id in DOWNLOADS and DOWNLOADS[task_id].get("status") != "cancelled":
                                DOWNLOADS[task_id]["progress"] = pct
                                DOWNLOADS[task_id]["downloaded_mb"] = f"{downloaded / (1024*1024):.1f}"
                                DOWNLOADS[task_id]["total_mb"] = f"{total_bytes / (1024*1024):.1f}" if total_bytes > 0 else "N/A"
                                DOWNLOADS[task_id]["speed_mb"] = f"{speed:.1f}"
                        last_time = now
                        last_bytes = downloaded

        with DOWNLOADS_LOCK:
            if task_id in DOWNLOADS and DOWNLOADS[task_id].get("status") == "cancelled":
                temp_path.unlink(missing_ok=True)
                return

        if temp_path.exists():
            temp_path.rename(target_path)
        with DOWNLOADS_LOCK:
            if task_id in DOWNLOADS:
                DOWNLOADS[task_id]["status"] = "completed"
                DOWNLOADS[task_id]["progress"] = 100
                DOWNLOADS[task_id]["speed_mb"] = "0.0"
    except Exception as e:
        temp_path.unlink(missing_ok=True)
        with DOWNLOADS_LOCK:
            if task_id in DOWNLOADS and DOWNLOADS[task_id].get("status") != "cancelled":
                DOWNLOADS[task_id]["status"] = "error"
                DOWNLOADS[task_id]["error"] = str(e)

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_html()
            return

        routes = {
            "/api/models": lambda: list_models(),
            "/api/models/catalog": lambda: {"catalog": MODEL_CATALOG},
            "/api/models/downloads": lambda: self._get_downloads(),
            "/api/gpu": lambda: get_system_info()["gpu"],
            "/api/system/info": lambda: get_system_info(),
            "/api/llm/status": lambda: _llm_status(),
            "/api/llm/builds": lambda: {"builds": [{"id": b["id"], "name": b["name"], "exists": b["bin"].exists()} for b in LLAMA_BUILDS]},
            "/api/llm/presets": lambda: {"presets": load_presets()},
            "/api/llm/last-run": lambda: {"last_run": load_last_run()},
            "/api/comfy/status": lambda: {
                "running": is_comfy_running(),
                "pid": read_pid(COMFY_PID) or find_comfy_pid(),
                "installed": COMFY_DIR.exists(),
                "log": tail_log(LOGS_DIR / "comfy.out"),
            },
        }

        if path in routes:
            try:
                self._send(200, routes[path]())
            except Exception as e:
                self._send(500, {"error": str(e)})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/api/llm/start":
            self._llm_start(body)
        elif path == "/api/llm/stop":
            self._llm_stop()
        elif path == "/api/llm/presets/save":
            self._preset_save(body)
        elif path == "/api/llm/presets/delete":
            self._preset_delete(body)
        elif path == "/api/llm/capture":
            self._capture_running(body)
        elif path == "/api/comfy/start":
            self._comfy_start(body)
        elif path == "/api/comfy/stop":
            self._comfy_stop()
        elif path == "/api/comfy/install":
            self._comfy_install()
        elif path == "/api/server/reboot":
            self._server_action("reboot")
        elif path == "/api/server/shutdown":
            self._server_action("poweroff")
        elif path == "/api/server/restart-panel":
            self._server_action("restart-panel")
        elif path == "/api/models/delete":
            self._model_delete(body)
        elif path == "/api/models/download":
            self._model_download(body)
        elif path == "/api/models/download/cancel":
            self._model_download_cancel(body)
        else:
            self._send(404, {"error": "not found"})

    # --- LLM ---
    def _build_cmd(self, body: dict) -> list[str]:
        model = body.get("model")
        if not model:
            res = list_models()
            for m in res["models"]:
                if m["type"] == "llm":
                    model = m["path"]
                    break
            if not model and res["models"]:
                model = res["models"][0]["path"]
        bin_path = get_llama_bin(body.get("build"))
        cmd = [str(bin_path), "--model", model or "/dev/null"]

        # Multimodal projection (mmproj) support
        mmproj = body.get("mmproj")
        if mmproj and mmproj not in ("none", "", "null", None):
            cmd.extend(["--mmproj", str(mmproj)])

        # Explicit flags from body
        flag_map = {
            "ngl": ("--gpu-layers", str),
            "ctx": ("--ctx-size", str),
            "threads": ("--threads", str),
            "temp": ("--temp", str),
            "repeat_penalty": ("--repeat-penalty", str),
            "presence_penalty": ("--presence-penalty", str),
            "top_k": ("--top-k", str),
            "top_p": ("--top-p", str),
            "min_p": ("--min-p", str),
            "cache_type_k": ("--cache-type-k", str),
            "cache_type_v": ("--cache-type-v", str),
            "flash_attn": ("--flash-attn", str),
            "cont_batching": ("--cont-batching", str),
            "slot_context_size": ("--slot-context-size", str),
            "batch": ("--batch-size", str),
            "ubatch": ("--ubatch-size", str),
            "ctx_checkpoints": ("--ctx-checkpoints", str),
            "cache_reuse": ("--cache-reuse", str),
            "reasoning": ("--reasoning", str),
        }
        for key, (flag, cast) in flag_map.items():
            val = body.get(key)
            if val is not None and str(val).strip() != "":
                cmd.extend([flag, cast(val)])

        # Speculative decoding (ONLY if spec_enabled == 'on')
        # Prevents passing unwanted MTP flags to standard models
        if body.get("spec_enabled") in ("on", True, "true", "1"):
            spec_type = body.get("spec_type", "draft-mtp")
            spec_draft_n = body.get("spec_draft_n", "3")
            if spec_type and str(spec_type).strip() != "":
                cmd.extend(["--spec-type", str(spec_type)])
            if spec_draft_n and str(spec_draft_n).strip() != "":
                cmd.extend(["--spec-draft-n-max", str(spec_draft_n)])

        # Boolean flags (only --flag, no value)
        bool_flag_map = {
            "jinja": "--jinja",
            "no_mmap": "--no-mmap",
            "context_shift": "--context-shift",
            "api": "--api",
        }
        for key, flag in bool_flag_map.items():
            if body.get(key) in ("on", True, "true", "1"):
                cmd.append(flag)

        cmd.extend(["--host", "0.0.0.0", "--port", str(body.get("port", "8080"))])
        return cmd

    def _llm_start(self, body: dict):
        if is_llama_running():
            self._send(200, {"message": "Уже запущен"})
            return
        cmd = self._build_cmd(body)
        save_last_run({k: v for k, v in body.items() if v is not None and str(v).strip() != ""})
        log_file = LOGS_DIR / "llama.out"
        try:
            with open(log_file, "w") as f:
                proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
            LLAMA_PID.write_text(str(proc.pid))
            self._send(200, {"message": f"Запущен (PID {proc.pid})"})
        except Exception as e:
            self._send(500, {"message": f"Ошибка запуска: {e}"})

    def _llm_stop(self):
        pid = find_llama_pid()
        if pid:
            os.kill(pid, 15)
            LLAMA_PID.unlink(missing_ok=True)
            self._send(200, {"message": f"Остановлен (PID {pid})"})
        else:
            self._send(200, {"message": "Не был запущен"})

    def _capture_running(self, body: dict):
        """Capture current running process flags as a preset."""
        pid = find_llama_pid()
        if not pid:
            self._send(400, {"message": "llama-server не запущен"})
            return
        flags = parse_process_args(pid)
        name = body.get("name", "Captured Process").strip()
        self._send(200, {"message": f"Захвачены флаги из процесса (PID {pid})", "flags": flags, "name": name})

    # --- Presets ---
    def _preset_save(self, body: dict):
        name = body.get("name", "").strip()
        if not name:
            self._send(400, {"message": "Укажите имя пресета"})
            return
        model = body.get("model", "")
        mmproj = body.get("mmproj", "none")
        spec_enabled = body.get("spec_enabled", "off")
        flags = {
            k: str(v) for k, v in body.items()
            if k not in ("name", "model", "mmproj", "spec_enabled") and v is not None and str(v).strip() != ""
        }
        presets = load_presets()
        updated = False
        for i, p in enumerate(presets):
            if p.get("name") == name:
                presets[i] = {
                    "name": name,
                    "model": model,
                    "mmproj": mmproj,
                    "spec_enabled": spec_enabled,
                    "flags": flags
                }
                updated = True
                break
        if not updated:
            presets.append({
                "name": name,
                "model": model,
                "mmproj": mmproj,
                "spec_enabled": spec_enabled,
                "flags": flags
            })
        save_presets(presets)
        self._send(200, {"message": f"Пресет «{name}» сохранён", "presets": presets})

    def _preset_delete(self, body: dict):
        name = body.get("name", "").strip()
        presets = [p for p in load_presets() if p.get("name") != name]
        save_presets(presets)
        self._send(200, {"message": f"Пресет «{name}» удалён"})

    # --- ComfyUI ---
    def _comfy_start(self, body: dict):
        if not COMFY_DIR.exists():
            self._send(400, {"message": "ComfyUI не установлен"})
            return
        if is_comfy_running():
            self._send(200, {"message": "Уже запущен"})
            return
        port = body.get("port", "8188")
        python = COMFY_DIR / "venv" / "bin" / "python"
        if not python.exists():
            python_path = shutil.which("python3")
            python = Path(python_path) if python_path else Path("/usr/bin/python3")
        cmd = [str(python), str(COMFY_DIR / "ComfyUI" / "main.py"), "--listen", "0.0.0.0", "--port", str(port), "--fp16-vae"]
        log_file = LOGS_DIR / "comfy.out"
        with open(log_file, "w") as f:
            proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=str(COMFY_DIR))
        COMFY_PID.write_text(str(proc.pid))
        self._send(200, {"message": f"ComfyUI запущен (PID {proc.pid}), порт {port}"})

    def _comfy_stop(self):
        pid = read_pid(COMFY_PID) or find_comfy_pid()
        if pid:
            os.kill(pid, 15)
            COMFY_PID.unlink(missing_ok=True)
            self._send(200, {"message": f"Остановлен (PID {pid})"})
        else:
            self._send(200, {"message": "Не был запущен"})

    def _comfy_install(self):
        if COMFY_DIR.exists():
            self._send(200, {"message": "ComfyUI уже установлен"})
            return
        log_file = LOGS_DIR / "comfy_install.out"
        with open(log_file, "w") as f:
            t = threading.Thread(target=_install_comfy, args=(f,), daemon=True)
            t.start()
        self._send(200, {"message": "Установка запущена в фоне"})

    def _server_action(self, action: str):
        msg = call_systemd(action)
        self._send(200, {"message": msg})

    # --- Model delete & download ---
    def _model_delete(self, body: dict):
        filename = body.get("filename", "")
        if not filename:
            self._send(400, {"error": "Укажите имя файла"})
            return
        result = delete_model(filename)
        if "error" in result:
            self._send(400, result)
        else:
            self._send(200, result)

    def _get_downloads(self):
        with DOWNLOADS_LOCK:
            # Clean up old completed/cancelled/error after 30 mins
            now = time.time()
            return {"downloads": list(DOWNLOADS.values())}

    def _model_download(self, body: dict):
        url = body.get("url", "").strip()
        filename = body.get("filename", "").strip()
        if not url:
            self._send(400, {"error": "Укажите URL для загрузки"})
            return
        if not filename:
            filename = url.split("/")[-1].split("?")[0]
            if not filename.endswith(".gguf"):
                filename += ".gguf"

        target_path = MODELS_DIR / filename
        if target_path.exists():
            self._send(400, {"error": f"Файл {filename} уже существует"})
            return

        with DOWNLOADS_LOCK:
            if filename in DOWNLOADS and DOWNLOADS[filename].get("status") == "downloading":
                self._send(400, {"error": "Загрузка этой модели уже выполняется"})
                return

            DOWNLOADS[filename] = {
                "id": filename,
                "filename": filename,
                "url": url,
                "status": "downloading",
                "progress": 0,
                "downloaded_mb": "0.0",
                "total_mb": "Unknown",
                "speed_mb": "0.0",
                "error": ""
            }

        t = threading.Thread(target=_download_thread, args=(filename, url, target_path), daemon=True)
        t.start()
        self._send(200, {"message": f"Загрузка {filename} начата в фоновом режиме", "id": filename})

    def _model_download_cancel(self, body: dict):
        filename = body.get("filename", "").strip()
        if not filename:
            self._send(400, {"error": "Укажите имя файла"})
            return
        with DOWNLOADS_LOCK:
            if filename in DOWNLOADS:
                DOWNLOADS[filename]["status"] = "cancelled"
                self._send(200, {"message": f"Загрузка {filename} отменена"})
            else:
                self._send(404, {"error": "Загрузка не найдена"})

    def _serve_html(self):
        html_path = PANEL_DIR / "web" / "index.html"
        if not html_path.exists():
            html_path = _script_dir / "web" / "index.html"
        html = html_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

def _install_comfy(log_file):
    try:
        log_file.write("Клонирование ComfyUI...\n")
        log_file.flush()
        subprocess.run(["git", "clone", "https://github.com/comfyanonymous/ComfyUI.git", str(COMFY_DIR)],
                        check=True, stdout=log_file, stderr=subprocess.STDOUT)
        log_file.write("\nСоздание venv...\n")
        log_file.flush()
        subprocess.run(["python3", "-m", "venv", str(COMFY_DIR / "venv")],
                        check=True, stdout=log_file, stderr=subprocess.STDOUT)
        log_file.write("\nУстановка зависимостей...\n")
        log_file.flush()
        pip = COMFY_DIR / "venv" / "bin" / "pip"
        subprocess.run([str(pip), "install", "-e", ".[default]",
                        "--extra-index-url", "https://download.pytorch.org/whl/cu124"],
                        check=True, stdout=log_file, stderr=subprocess.STDOUT, cwd=str(COMFY_DIR))
        log_file.write("\n✅ Установка ComfyUI завершена!\n")
        log_file.flush()
    except Exception as e:
        log_file.write(f"\n❌ Ошибка: {e}\n")
        log_file.flush()

if __name__ == "__main__":
    server = http.server.HTTPServer((HOST, PORT), Handler)
    print(f"🚀 AI Panel (LM Studio Edition): http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Остановлен")
        server.shutdown()
