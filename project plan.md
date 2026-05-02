# Indic Subtitle Tool — Project Plan for Claude Code

## Project Overview

A web-based subtitle generation tool for Indian-language content creators. Users paste a YouTube URL, select a language, and receive a downloadable `.srt` or `.vtt` subtitle file. The tool is built around OpenAI Whisper (via `faster-whisper`) with `WhisperX` for word-level timestamp alignment.

---

## Developer Environment

| Property | Value |
|---|---|
| OS | Windows 11 |
| GPU | NVIDIA GeForce RTX 2060 SUPER (8GB VRAM) |
| CUDA | 12.4 |
| Python | 3.10 (Conda env: `subtitle-tool`) |
| PyTorch | cu124 build |
| ffmpeg | Standalone install at `C:\ffmpeg\bin` |
| IDE | VS Code |

---

## Target Users

Indian YouTube and Instagram creators making content in:
- Tamil, Telugu, Kannada, Malayalam (primary)
- Indian English (baseline — works out of the box)
- Code-mixed speech (e.g. Tamil-English, Telugu-English)

---

## Core User Flow

```
User pastes YouTube URL
        ↓
Backend downloads audio via yt-dlp
        ↓
faster-whisper large-v3 transcribes audio (CUDA)
        ↓
Segments converted to SRT / VTT format
        ↓
User downloads subtitle file
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| STT Model | `faster-whisper` large-v3 (CUDA, float16) |
| Subtitle alignment | `WhisperX` (VAD + word timestamps) |
| Audio extraction | `yt-dlp` + `ffmpeg` |
| Backend | `FastAPI` (Python) |
| Frontend | Plain HTML + vanilla JS (single page) |
| Task queue | Python `threading` (simple) → upgrade to Celery later |
| Future STT upgrade | Sarvam Saaras v3 API (Phase 3) |

---

## Project Structure

```
subtitle-tool/
├── PROJECT_PLAN.md          ← this file
├── requirements.txt
├── main.py                  ← FastAPI app entry point
├── pipeline/
│   ├── __init__.py
│   ├── downloader.py        ← yt-dlp audio download logic
│   ├── transcriber.py       ← faster-whisper transcription logic
│   └── formatter.py         ← SRT / VTT file generation
├── static/
│   └── index.html           ← single-page frontend
├── outputs/                 ← generated subtitle files (gitignored)
└── tests/
    ├── test_downloader.py
    ├── test_transcriber.py
    └── test_formatter.py
```

---

## Dependencies

Create `requirements.txt` with:

```
faster-whisper
whisperx
yt-dlp
fastapi
uvicorn
python-multipart
aiofiles
```

Install with:
```bash
conda activate subtitle-tool
pip install -r requirements.txt
```

> Note: PyTorch must be installed separately with CUDA support BEFORE installing the above:
> ```bash
> pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
> ```

---

## Module Specifications

### `pipeline/downloader.py`

```python
# Responsibilities:
# - Accept a YouTube URL as input
# - Use yt-dlp to download audio as WAV
# - Point yt-dlp to ffmpeg at C:\ffmpeg\bin
# - Return the path to the downloaded audio file
# - Handle errors: invalid URL, private video, unavailable video
# - Clean up downloaded audio file after transcription is complete

FFMPEG_LOCATION = r"C:\ffmpeg\bin"
OUTPUT_DIR = "outputs"
```

### `pipeline/transcriber.py`

```python
# Responsibilities:
# - Load faster-whisper large-v3 model on CUDA with float16
# - Accept audio file path and optional language hint
# - Use VAD filter to reduce hallucinations on silence
# - Return list of segments with start time, end time, text
# - Handle long audio via faster-whisper's built-in chunking
# - Log detected language and confidence score

MODEL_SIZE = "large-v3"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"
BEAM_SIZE = 5
VAD_FILTER = True
VAD_MIN_SILENCE_MS = 500
```

### `pipeline/formatter.py`

```python
# Responsibilities:
# - Accept list of segments (start, end, text)
# - Generate valid .srt file content as a string
# - Generate valid .vtt file content as a string
# - Write file to outputs/ directory
# - Return file path for download

# SRT timestamp format: HH:MM:SS,mmm --> HH:MM:SS,mmm
# VTT timestamp format: HH:MM:SS.mmm --> HH:MM:SS.mmm
```

### `main.py` — FastAPI backend

```python
# Endpoints:
#
# POST /transcribe
#   - Body: { "url": "https://youtube.com/...", "language": "ta", "format": "srt" }
#   - language options: "auto", "ta", "te", "kn", "ml", "en"
#   - format options: "srt", "vtt"
#   - Returns: { "job_id": "uuid", "status": "processing" }
#
# GET /status/{job_id}
#   - Returns: { "status": "processing" | "done" | "error", "download_url": "..." }
#
# GET /download/{job_id}
#   - Returns: the subtitle file as a download
#
# Simple in-memory job store (dict) for Phase 1
# Run transcription in a background thread
# CORS enabled for local frontend development
```

### `static/index.html` — Frontend

```
UI requirements:
- Single page, no frameworks, plain HTML + CSS + vanilla JS
- Input field: paste YouTube URL
- Dropdown: language selector (Auto-detect, Tamil, Telugu, Kannada, Malayalam, English)
- Dropdown: output format (SRT, VTT)
- Button: "Generate Subtitles"
- Status area: show "Processing..." while waiting, poll /status every 3 seconds
- Download button: appears when status is "done"
- Error message area: show friendly error if something goes wrong
- Keep the UI minimal and clean — this is a tool, not a product yet
```

---

## Phase 1 Success Criteria

Claude Code should verify these work before considering Phase 1 complete:

1. `python main.py` starts the FastAPI server without errors
2. Opening `http://localhost:8000` shows the UI
3. Pasting a YouTube URL and clicking Generate produces a valid `.srt` file
4. The `.srt` file has correct timestamps and readable text
5. An Indian English YouTube video transcribes with >80% accuracy visually
6. A Tamil or Telugu video attempts transcription (quality noted, not a pass/fail)

---

## Known Issues & Constraints

- **ffmpeg path is hardcoded** to `C:\ffmpeg\bin` — this is intentional for Phase 1. Make it a config variable in Phase 2.
- **No authentication** — this is a local dev tool in Phase 1, not a public server.
- **8GB VRAM limit** — large-v3 uses ~4-5GB. For videos longer than ~40 minutes, chunking may be needed. Add a max duration check (warn user if video > 30 minutes).
- **In-memory job store** — jobs are lost on server restart. Acceptable for Phase 1.
- **yt-dlp JS runtime warning** — a WARNING about no JS runtime will appear in logs. This is non-fatal, audio still downloads. Do not suppress it.
- **Model download on first run** — large-v3 is ~3GB and downloads automatically on first transcription. Expected behaviour.

---

## Language Codes Reference

| Language | Code for Whisper |
|---|---|
| Auto-detect | None (omit language param) |
| Tamil | `ta` |
| Telugu | `te` |
| Kannada | `kn` |
| Malayalam | `ml` |
| Hindi | `hi` |
| Indian English | `en` |

---

## Running the Project

```bash
# 1. Activate environment
conda activate subtitle-tool

# 2. Navigate to project folder
cd d:\subtitles-tool

# 3. Install dependencies (if not already done)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt

# 4. Start the server
python main.py

# 5. Open browser
# http://localhost:8000
```

---

## Phase Roadmap

### Phase 1 — Local working pipeline (current)
- [x] Environment setup (CUDA, PyTorch, faster-whisper)
- [ ] `downloader.py` — yt-dlp audio extraction
- [ ] `transcriber.py` — faster-whisper CUDA transcription
- [ ] `formatter.py` — SRT + VTT output
- [ ] `main.py` — FastAPI with background jobs
- [ ] `index.html` — minimal frontend UI
- [ ] End-to-end test on Indian English video
- [ ] End-to-end test on Tamil / Telugu video
- [ ] Document failure cases for South Indian languages

### Phase 2 — Shareable web tool
- [ ] Replace hardcoded ffmpeg path with config
- [ ] Add proper job queue (Celery or Redis)
- [ ] Handle videos up to 1 hour
- [ ] Deploy to Railway or Render
- [ ] Share with 2-3 real creators for feedback

### Phase 3 — Model upgrade + validation
- [ ] Integrate Sarvam Saaras v3 API as alternative backend
- [ ] A/B test Whisper vs Sarvam on South Indian content
- [ ] Language auto-detection improvements
- [ ] Iterate UI based on creator feedback
- [ ] Go / no-go decision on building seriously

---

## Notes for Claude Code

- Build one module at a time in this order: `formatter.py` → `transcriber.py` → `downloader.py` → `main.py` → `index.html`
- Test each module independently before wiring them together
- The `outputs/` directory should be created automatically if it doesn't exist
- All file paths should use `pathlib.Path` not string concatenation
- Print progress to console during transcription so the developer can see what's happening
- Do not install any new packages not listed in `requirements.txt` without flagging it first