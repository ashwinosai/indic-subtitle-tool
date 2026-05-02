# 🎙 Indic Subtitle Tool

> Generate accurate subtitles for Indian-language YouTube videos — powered by OpenAI Whisper, running locally on your GPU.

![Python](https://img.shields.io/badge/Python-3.10-blue?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal?style=flat-square&logo=fastapi&logoColor=white)
![CUDA](https://img.shields.io/badge/CUDA-12.4-green?style=flat-square&logo=nvidia&logoColor=white)
![Whisper](https://img.shields.io/badge/Whisper-large--v3-orange?style=flat-square)
![Phase](https://img.shields.io/badge/Phase-1%20%E2%80%94%20Local%20Dev-purple?style=flat-square)

---

## What it does

Paste a YouTube URL. Get a subtitle file. That's it.

The tool downloads the audio, runs it through OpenAI's Whisper large-v3 model on your local GPU, and hands you a ready-to-use `.srt` or `.vtt` file — no API keys, no cloud, no cost per minute.

Built for **Indian YouTube creators** making content in Tamil, Telugu, Kannada, Malayalam, Hindi, and Indian English.

---

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Browser                             │
│                                                                 │
│   Paste YouTube URL  →  Click Generate  →  Download .srt/.vtt  │
└───────────────────────────────┬─────────────────────────────────┘
                                │  POST /transcribe
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Server (main.py)                   │
│                                                                 │
│   Creates job ID  →  Spawns background thread  →  Returns ID   │
│   Browser polls /status every 3 seconds                         │
└───┬───────────────────────────┬───────────────────────────┬─────┘
    │                           │                           │
    ▼                           ▼                           ▼
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ downloader   │     │   transcriber    │     │   formatter     │
│    .py       │ ──▶ │      .py         │ ──▶ │     .py         │
│              │     │                  │     │                 │
│ yt-dlp       │     │ faster-whisper   │     │ Segments        │
│ + ffmpeg     │     │ large-v3         │     │ → SRT / VTT     │
│              │     │ CUDA float16     │     │                 │
│ YouTube URL  │     │ VAD filter       │     │ outputs/        │
│ → WAV file   │     │ → [{start, end,  │     │ job-id.srt      │
│              │     │    text}, ...]   │     │                 │
└──────────────┘     └──────────────────┘     └─────────────────┘
```

---

## Supported Languages

| Language       | Code  |
|----------------|-------|
| Auto-detect    | —     |
| Tamil          | `ta`  |
| Telugu         | `te`  |
| Kannada        | `kn`  |
| Malayalam      | `ml`  |
| Hindi          | `hi`  |
| Indian English | `en`  |

---

## Requirements

| Component | Requirement                          |
|-----------|--------------------------------------|
| OS        | Windows 11                           |
| GPU       | NVIDIA with 6GB+ VRAM (tested on RTX 2060 SUPER) |
| CUDA      | 12.4                                 |
| Python    | 3.10 via Conda                       |
| ffmpeg    | Installed at `C:\ffmpeg\bin`         |

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/YOUR_USERNAME/subtitles-tool.git
cd subtitles-tool
```

**2. Create and activate the Conda environment**
```bash
conda create -n subtitle-tool python=3.10
conda activate subtitle-tool
```

**3. Install PyTorch with CUDA support**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```
> ⚠️ Do this step *before* installing other requirements. Installing from PyPI will give you the CPU-only build.

**4. Install remaining dependencies**
```bash
pip install -r requirements.txt
```

**5. Start the server**
```bash
python main.py
```

Open **http://localhost:8000** in your browser.

> 🔔 On first run, Whisper will download the large-v3 model (~3 GB). This happens once and is then cached locally.

---

## Project Structure

```
subtitles-tool/
├── main.py                ← FastAPI server — wires everything together
├── requirements.txt
├── pipeline/
│   ├── downloader.py      ← YouTube audio extraction (yt-dlp + ffmpeg)
│   ├── transcriber.py     ← Whisper transcription (CUDA, float16)
│   └── formatter.py       ← Converts segments to SRT / VTT
├── static/
│   └── index.html         ← Single-page frontend (no frameworks)
└── outputs/               ← Generated subtitle files (git-ignored)
```

---

## Tech Stack

| Layer        | Technology                                  |
|--------------|---------------------------------------------|
| AI Model     | `faster-whisper` large-v3 — CUDA, float16  |
| Audio        | `yt-dlp` + `ffmpeg`                         |
| Backend      | `FastAPI` + `uvicorn`                       |
| Jobs         | Python `threading` (in-memory store)        |
| Frontend     | Plain HTML + vanilla JS                     |

---

## Known Limitations (Phase 1)

- **Music videos** — Whisper detects no speech in music-only videos. Use videos with spoken dialogue.
- **30-minute cap** — Videos longer than 30 minutes will show a warning (still processes, just slower).
- **ffmpeg path is hardcoded** to `C:\ffmpeg\bin` — will be made configurable in Phase 2.
- **Jobs reset on restart** — The in-memory job store is lost when the server stops. Acceptable for local use.
- **Single user** — No queue management. Submit one job at a time for best results.

---

## Roadmap

- [x] **Phase 1** — Local working pipeline
- [ ] **Phase 2** — Shareable web tool (Celery queue, config file, deploy to Railway/Render)
- [ ] **Phase 3** — Sarvam Saaras v3 API integration for improved South Indian language accuracy

---

## Acknowledgements

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — 4× faster Whisper inference via CTranslate2
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube audio extraction
- [OpenAI Whisper](https://github.com/openai/whisper) — the underlying speech recognition model
