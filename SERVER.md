# AI Server — Technical Documentation

> Generated: 2026-08-09

---

## Hardware

| Component | Specification |
|---|---|
| **CPU** | AMD Ryzen 7 3700X (8 cores / 16 threads, up to 4.43 GHz) |
| **GPU** | NVIDIA Tesla V100-SXM2-32GB (Volta, NVLink) |
| **GPU Power Limit** | 230W (locked via `nvidia-powerlimit.service`) |
| **RAM** | 32 GB DDR4 |
| **Storage** | NVMe 465.8 GB (ext4, LVM) |
| **Network** | 192.168.137.10/24 (enp4s0) |

## OS & Drivers

| Component | Version |
|---|---|
| **OS** | Ubuntu 24.04.4 LTS (Noble Numbat) |
| **Kernel** | 6.8.0-137-generic |
| **GPU Driver** | 580.173.02 |
| **CUDA** | 12.4 (via driver, no separate toolkit) |

---

## Services

### AI Panel (`ai-panel.service`) — **enabled**

Web-панель для управления LLM и ComfyUI.

| Параметр | Значение |
|---|---|
| **Порт** | 7860 |
| **URL** | http://192.168.137.10:7860 |
| **User** | dima |
| **Exec** | `/usr/bin/python3 /home/dima/ai-panel/server.py` |
| **Restart** | on-failure (5s delay) |
| **Файлы** | `~/ai-panel/server.py`, `~/ai-panel/web/index.html` |

**Возможности панели:**
- Запуск/остановка llama-server с настраиваемыми флагами
- Управление ComfyUI (start/stop/install)
- Мониторинг GPU (температура, VRAM)
- Пресеты конфигурации, захват флагов из запущенного процесса
- Перезагрузка/выключение сервера
- Удаление моделей из `~/models`

### NVIDIA Power Limit (`nvidia-powerlimit.service`) — **disabled**

Ограничивает GPU до 230W. Запускается как oneshot при старте системы.

```
nvidia-smi -pm 1 && nvidia-smi -pl 230
```

### llama-server

Запускается через AI Panel (не как отдельный systemd-сервис).

| Параметр | Значение |
|---|---|
| **Бинарник** | `~/llama.cpp/build/bin/llama-server` (CUDA build, ~18 MB) |
| **Порт** | 8080 |
| **PID файл** | `~/ai-panel/logs/llama.pid` |
| **Лог** | `~/ai-panel/logs/llama.out` |

### ComfyUI

| Параметр | Значение |
|---|---|
| **Директория** | `~/Comfyui/ComfyUI/` |
| **Venv** | `~/Comfyui/venv/` |
| **Порт** | 8188 |
| **URL** | http://192.168.137.10:8188 |
| **PID файл** | `~/ai-panel/logs/comfy.pid` |
| **Лог** | `~/ai-panel/logs/comfy.out` |

---

## Models

GGUF-модели хранятся в `~/models/`.

| Model | Size | Quantization |
|---|---|---|
| Qwen3.6-27B-Q5_K_M.gguf | 19 GB | Q5_K_M |
| Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf | 6.7 GB | Q4_K_M |

---

## Presets

Сохранены в `~/ai-panel/presets.json`.

### «кодинг 196608»

| Flag | Value |
|---|---|
| Model | Qwen3.6-27B-Q5_K_M.gguf |
| GPU layers (-ngl) | 99 (все на GPU) |
| Context (-c) | 196608 (~192K) |
| Threads (-t) | 12 |
| Temperature | 0.6 |
| Repeat penalty | 1.0 |
| KV cache | q8_0 |
| Flash attention | on |
| Batch / Ubatch | 1024 / 256 |
| Speculative | draft-mtp, 3 draft tokens |
| Jinja | on |
| No mmap | on |
| Context shift | on |

---

## Directory Structure

```
/home/dima/
├── ai-panel/
│   ├── server.py              # HTTP server (Python stdlib)
│   ├── presets.json           # Saved launch presets
│   ├── last_run.json          # Last launch config
│   ├── ai-panel.service       # systemd unit
│   ├── ai-panel-sudoers       # sudoers rules
│   ├── SERVER.md              # This file
│   ├── web/
│   │   └── index.html         # Frontend (vanilla JS, inline CSS)
│   ├── logs/
│   │   ├── llama.out          # llama-server log
│   │   ├── llama.pid          # Current PID
│   │   └── comfy.out          # ComfyUI log
│   └── scripts/
│       ├── llama.sh           # CLI wrapper for llama-server
│       ├── 99-ai-panel-sudoers
│       ├── setup-nvidia-powerlimit.sh
│       └── nvidia-powerlimit.service
├── models/                    # GGUF model files
├── llama.cpp/                 # llama.cpp source + build (CUDA)
└── Comfyui/                   # ComfyUI + venv
```

---

## Useful Commands

```bash
# Restart panel
sudo systemctl restart ai-panel

# Check status
sudo systemctl status ai-panel

# View panel log
tail -f ~/ai-panel/logs/panel.out

# View llama-server log
tail -f ~/ai-panel/logs/llama.out

# GPU info
nvidia-smi

# Power limit
nvidia-smi -pl 230
```

---

## Sudo Privileges (passwordless)

File: `/etc/sudoers.d/ai-panel`

- `systemctl restart/stop ai-panel`
- `shutdown -r/-h`
- `nvidia-smi`

---

## Notes

- **GPU power locked at 230W** — prevents thermal throttling on server PSU
- **No external Python dependencies** — panel uses only stdlib (urllib, http.server, etc.)
