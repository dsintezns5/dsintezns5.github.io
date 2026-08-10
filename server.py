#!/usr/bin/env python3
"""AI Panel — lightweight management server for llama.cpp and ComfyUI."""

import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import urllib.parse
from pathlib import Path

# gai.conf is configured to prefer IPv4 (precedence ::ffff:0:0/96  100).
# No socket override needed — DNS resolves IPv4 first system-wide.

HOME = Path.home()
PANEL_DIR = HOME / "ai-panel"
LOGS_DIR = PANEL_DIR / "logs"
MODELS_DIR = HOME / "models"
LLAMA_DIR = HOME / "llama.cpp"
LLAMA_PID = LOGS_DIR / "llama.pid"

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
COMFY_PID = LOGS_DIR / "comfy.pid"
COMFY_DIR = HOME / "Comfyui"
PRESETS_FILE = PANEL_DIR / "presets.json"
LAST_RUN_FILE = PANEL_DIR / "last_run.json"

LOGS_DIR.mkdir(exist_ok=True)

PORT = int(os.environ.get("PANEL_PORT", "7860"))
HOST = os.environ.get("PANEL_HOST", "0.0.0.0")

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
    """Find running ComfyUI process via pgrep (matches python processes running main.py in Comfyui dir)."""
    try:
        r = subprocess.run(["pgrep", "-nf", "Comfyui.*main\\.py"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return int(r.stdout.strip())
    except Exception:
        pass
    return None


def is_llama_running() -> bool:
    return find_llama_pid() is not None


def is_running(path: Path) -> bool:
    return read_pid(path) is not None


def is_comfy_running() -> bool:
    """Check if ComfyUI is running: first via PID file, then via pgrep fallback."""
    if read_pid(COMFY_PID):
        return True
    return find_comfy_pid() is not None


def tail_log(path: Path, lines: int = 50) -> str:
    if not path.exists():
        return "Лог-файл не найден"
    with open(path) as f:
        all_lines = f.readlines()
    return "".join(all_lines[-lines:]).strip() or "Пусто"


def list_models() -> list[dict]:
    models = []
    for f in sorted(MODELS_DIR.glob("*.gguf")):
        size = f.stat().st_size
        gb = size / (1024**3)
        models.append({"name": f.name, "path": str(f), "size": f"{gb:.1f} GB"})
    return models


def run_cmd(cmd: list[str], timeout: int = 30) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()


def get_gpu_info() -> dict:
    out = run_cmd(["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,memory.total", "--format=csv,noheader"])
    if out:
        parts = out.split(",")
        if len(parts) >= 3:
            temp = parts[0].strip().replace(" C", "")
            used_mb = parts[1].strip().replace(" MiB", "")
            total_mb = parts[2].strip().replace(" MiB", "")
            try:
                return {"temperature": temp, "memory_used_gb": str(round(int(used_mb) / 1024, 1)), "memory_total": total_mb}
            except ValueError:
                pass
    return {}


def parse_process_args(pid: int) -> dict:
    """Parse running llama-server process args into a flags dict."""
    try:
        r = subprocess.run(["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True)
        args = r.stdout
        result = {"port": "8080"}
        m = re.search(r"-m\s+(\S+)", args)
        if m:
            result["model"] = m.group(1)
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
        return result
    except Exception:
        return {}


def _llm_status() -> dict:
    pid = find_llama_pid()
    running = pid is not None
    info = {"running": running, "pid": pid, "flags": {}, "build": ""}
    if running:
        info["flags"] = parse_process_args(pid)
        info["port"] = info["flags"].get("port", "8080")
        info["model"] = Path(info["flags"].get("model", "")).name if info["flags"].get("model") else ""
        # Detect which build binary is running
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
    info["log"] = tail_log(LOGS_DIR / "llama.out")
    return info


# --- Presets ---
def load_presets() -> list[dict]:
    if PRESETS_FILE.exists():
        try:
            return json.loads(PRESETS_FILE.read_text())
        except Exception:
            return []
    return []


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
        return "systemctl не найден"
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


def _format_size(b: int) -> str:
    if b < 1024 * 1024:
        return f"{b / 1024:.0f} MB"
    return f"{b / (1024**3):.1f} GB"


def delete_model(filename: str) -> dict:
    """Delete a model file from ~/models."""
    path = MODELS_DIR / filename
    if not path.exists():
        return {"error": f"Файл не найден: {filename}"}
    size = path.stat().st_size
    path.unlink()
    return {"message": f"Удалён: {filename} ({_format_size(size)})"}


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
            "/api/models": lambda: {"models": list_models()},
            "/api/gpu": lambda: get_gpu_info(),
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
        else:
            self._send(404, {"error": "not found"})

    # --- LLM ---
    def _build_cmd(self, body: dict) -> list[str]:
        model = body.get("model")
        if not model:
            models = list_models()
            if models:
                model = models[0]["path"]
        bin_path = get_llama_bin(body.get("build"))
        cmd = [str(bin_path), "--model", model or "/dev/null"]

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
            "spec_type": ("--spec-type", str),
            "spec_draft_n": ("--spec-draft-n-max", str),
            "reasoning": ("--reasoning", str),
        }
        for key, (flag, cast) in flag_map.items():
            val = body.get(key)
            if val is not None and val != "":
                cmd.extend([flag, cast(val)])

        # Boolean flags (only --flag, no value)
        bool_flag_map = {
            "jinja": "--jinja",
            "no_mmap": "--no-mmap",
            "context_shift": "--context-shift",
            "api": "--api",
        }
        for key, flag in bool_flag_map.items():
            if body.get(key) == "on":
                cmd.append(flag)

        cmd.extend(["--host", "0.0.0.0", "--port", str(body.get("port", "8080"))])
        return cmd

    def _llm_start(self, body: dict):
        if is_llama_running():
            self._send(200, {"message": "Уже запущен"})
            return
        cmd = self._build_cmd(body)
        # Save last run
        save_last_run({k: v for k, v in body.items() if v is not None and v != ""})
        log_file = LOGS_DIR / "llama.out"
        with open(log_file, "w") as f:
            proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
        LLAMA_PID.write_text(str(proc.pid))
        self._send(200, {"message": f"Запущен (PID {proc.pid})"})

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
        name = body.get("name", "Captured")
        self._send(200, {"message": f"Захвачены флаги из процесса (PID {pid})", "flags": flags, "name": name})

    # --- Presets ---
    def _preset_save(self, body: dict):
        name = body.get("name", "Preset").strip()
        if not name:
            self._send(400, {"message": "Укажите имя пресета"})
            return
        flags = {k: v for k, v in body.items() if k not in ("name",) and v is not None and v != ""}
        presets = load_presets()
        # Update if exists
        for i, p in enumerate(presets):
            if p["name"] == name:
                presets[i] = {"name": name, "flags": flags}
                save_presets(presets)
                self._send(200, {"message": f"Пресет «{name}» обновлён"})
                return
        presets.append({"name": name, "flags": flags})
        save_presets(presets)
        self._send(200, {"message": f"Пресет «{name}» сохранён"})

    def _preset_delete(self, body: dict):
        name = body.get("name", "").strip()
        presets = [p for p in load_presets() if p["name"] != name]
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
            python = subprocess.which("python3")
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

    # --- Model delete ---
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

    def _serve_html(self):
        html = (PANEL_DIR / "web" / "index.html").read_bytes()
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
    print(f"🚀 AI Panel: http://192.168.137.10:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Остановлен")
        server.shutdown()
