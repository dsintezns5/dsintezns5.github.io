# AI Server вЂ” Technical Documentation

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

### AI Panel (`ai-panel.service`) вЂ” **enabled**

Web-РїР°РЅРµР»СЊ РґР»СЏ СѓРїСЂР°РІР»РµРЅРёСЏ LLM Рё ComfyUI.

| РџР°СЂР°РјРµС‚СЂ | Р—РЅР°С‡РµРЅРёРµ |
|---|---|
| **РџРѕСЂС‚** | 7860 |
| **URL** | http://192.168.137.10:7860 |
| **User** | dima |
| **Exec** | `/usr/bin/python3 /home/dima/ai-panel/server.py` |
| **Restart** | on-failure (5s delay) |
| **Р¤Р°Р№Р»С‹** | `~/ai-panel/server.py`, `~/ai-panel/web/index.html` |

**Р’РѕР·РјРѕР¶РЅРѕСЃС‚Рё РїР°РЅРµР»Рё:**
- Р—Р°РїСѓСЃРє/РѕСЃС‚Р°РЅРѕРІРєР° llama-server СЃ РЅР°СЃС‚СЂР°РёРІР°РµРјС‹РјРё С„Р»Р°РіР°РјРё
- РЈРїСЂР°РІР»РµРЅРёРµ ComfyUI (start/stop/install)
- РњРѕРЅРёС‚РѕСЂРёРЅРі GPU (С‚РµРјРїРµСЂР°С‚СѓСЂР°, VRAM)
- РџСЂРµСЃРµС‚С‹ РєРѕРЅС„РёРіСѓСЂР°С†РёРё, Р·Р°С…РІР°С‚ С„Р»Р°РіРѕРІ РёР· Р·Р°РїСѓС‰РµРЅРЅРѕРіРѕ РїСЂРѕС†РµСЃСЃР°
- РџРµСЂРµР·Р°РіСЂСѓР·РєР°/РІС‹РєР»СЋС‡РµРЅРёРµ СЃРµСЂРІРµСЂР°
- РЈРґР°Р»РµРЅРёРµ РјРѕРґРµР»РµР№ РёР· `~/models`

### NVIDIA Power Limit (`nvidia-powerlimit.service`) вЂ” **disabled**

РћРіСЂР°РЅРёС‡РёРІР°РµС‚ GPU РґРѕ 230W. Р—Р°РїСѓСЃРєР°РµС‚СЃСЏ РєР°Рє oneshot РїСЂРё СЃС‚Р°СЂС‚Рµ СЃРёСЃС‚РµРјС‹.

```
nvidia-smi -pm 1 && nvidia-smi -pl 230
```

### llama-server

Р—Р°РїСѓСЃРєР°РµС‚СЃСЏ С‡РµСЂРµР· AI Panel (РЅРµ РєР°Рє РѕС‚РґРµР»СЊРЅС‹Р№ systemd-СЃРµСЂРІРёСЃ).

| РџР°СЂР°РјРµС‚СЂ | Р—РЅР°С‡РµРЅРёРµ |
|---|---|
| **Р‘РёРЅР°СЂРЅРёРє** | `~/llama.cpp/build/bin/llama-server` (CUDA build, ~18 MB) |
| **РџРѕСЂС‚** | 8080 |
| **PID С„Р°Р№Р»** | `~/ai-panel/logs/llama.pid` |
| **Р›РѕРі** | `~/ai-panel/logs/llama.out` |

### ComfyUI

| РџР°СЂР°РјРµС‚СЂ | Р—РЅР°С‡РµРЅРёРµ |
|---|---|
| **Р”РёСЂРµРєС‚РѕСЂРёСЏ** | `~/Comfyui/ComfyUI/` |
| **Venv** | `~/Comfyui/venv/` |
| **РџРѕСЂС‚** | 8188 |
| **URL** | http://192.168.137.10:8188 |
| **PID С„Р°Р№Р»** | `~/ai-panel/logs/comfy.pid` |
| **Р›РѕРі** | `~/ai-panel/logs/comfy.out` |

---

## Models

GGUF-РјРѕРґРµР»Рё С…СЂР°РЅСЏС‚СЃСЏ РІ `~/models/`.

| Model | Size | Quantization |
|---|---|---|
| Qwen3.6-27B-Q5_K_M.gguf | 19 GB | Q5_K_M |
| Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf | 6.7 GB | Q4_K_M |

---

## Presets

РЎРѕС…СЂР°РЅРµРЅС‹ РІ `~/ai-panel/presets.json`.

### В«РєРѕРґРёРЅРі 196608В»

| Flag | Value |
|---|---|
| Model | Qwen3.6-27B-Q5_K_M.gguf |
| GPU layers (-ngl) | 99 (РІСЃРµ РЅР° GPU) |
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
в”њв”Ђв”Ђ ai-panel/
в”‚   в”њв”Ђв”Ђ server.py              # HTTP server (Python stdlib)
в”‚   в”њв”Ђв”Ђ presets.json           # Saved launch presets
в”‚   в”њв”Ђв”Ђ last_run.json          # Last launch config
в”‚   в”њв”Ђв”Ђ ai-panel.service       # systemd unit
в”‚   в”њв”Ђв”Ђ ai-panel-sudoers       # sudoers rules
в”‚   в”њв”Ђв”Ђ SERVER.md              # This file
в”‚   в”њв”Ђв”Ђ web/
в”‚   в”‚   в””в”Ђв”Ђ index.html         # Frontend (vanilla JS, inline CSS)
в”‚   в”њв”Ђв”Ђ logs/
в”‚   в”‚   в”њв”Ђв”Ђ llama.out          # llama-server log
в”‚   в”‚   в”њв”Ђв”Ђ llama.pid          # Current PID
в”‚   в”‚   в””в”Ђв”Ђ comfy.out          # ComfyUI log
в”‚   в””в”Ђв”Ђ scripts/
в”‚       в”њв”Ђв”Ђ llama.sh           # CLI wrapper for llama-server
в”‚       в”њв”Ђв”Ђ 99-ai-panel-sudoers
в”‚       в”њв”Ђв”Ђ setup-nvidia-powerlimit.sh
в”‚       в””в”Ђв”Ђ nvidia-powerlimit.service
в”њв”Ђв”Ђ models/                    # GGUF model files
в”њв”Ђв”Ђ llama.cpp/                 # llama.cpp source + build (CUDA)
в””в”Ђв”Ђ Comfyui/                   # ComfyUI + venv
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

- **GPU power locked at 230W** вЂ” prevents thermal throttling on server PSU
- **No external Python dependencies** вЂ” panel uses only stdlib (urllib, http.server, etc.)
