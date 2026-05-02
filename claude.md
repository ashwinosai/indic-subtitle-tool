# CLAUDE.md — Instructions for Claude Code

Read this file fully before doing anything else. These instructions override your defaults for this project.

---

## What this project is

A web-based subtitle generation tool for Indian-language YouTube creators. Users paste a YouTube URL and receive a downloadable SRT or VTT subtitle file. The full spec is in `PROJECT_PLAN.md` — read that too before writing any code.

---

## Developer environment

- OS: Windows 11
- GPU: NVIDIA RTX 2060 SUPER (8GB VRAM)
- CUDA: 12.4
- Python: 3.10 via Conda environment named `subtitle-tool`
- ffmpeg: installed at `C:\ffmpeg\bin` (standalone, not conda)
- All commands must be run with `subtitle-tool` conda environment active

To activate the environment in terminal:
```bash
conda activate subtitle-tool
```

---

## How to work

### Build in this exact order. Do not skip ahead.

1. `pipeline/formatter.py` — no dependencies, test immediately after
2. `pipeline/transcriber.py` — requires GPU, test with a local WAV file
3. `pipeline/downloader.py` — requires yt-dlp + ffmpeg, test with a short YouTube URL
4. `main.py` — wire all three together into FastAPI
5. `static/index.html` — frontend, test in browser last

### One module at a time

Build one module, write a simple test for it, confirm it works, then move to the next. Do not build multiple modules simultaneously.

### Test before wiring

Each module must be independently testable. Create a small `if __name__ == "__main__":` block at the bottom of each module for quick manual testing.

---

## Mandatory coding rules

- Use `pathlib.Path` for all file paths — no string concatenation for paths
- Create `outputs/` directory automatically if it does not exist
- Print progress to console during transcription (model loading, transcribing, writing file)
- All functions must have docstrings
- Handle these errors explicitly in every module:
  - File not found
  - CUDA not available (fall back to CPU with a warning)
  - Invalid or unavailable YouTube URL
  - Video longer than 30 minutes (warn the user, do not hard fail)

---

## Hardware constraints

- VRAM is 8GB — faster-whisper large-v3 uses ~4-5GB in float16
- Always use `device="cuda"` and `compute_type="float16"`
- If CUDA is unavailable, fall back to `device="cpu"` and `compute_type="int8"` with a console warning
- Do not load the model more than once — load it at app startup and reuse it

---

## ffmpeg configuration

ffmpeg is NOT on the system PATH due to a conda gdk-pixbuf conflict on this machine. Always pass the location explicitly:

```python
FFMPEG_LOCATION = r"C:\ffmpeg\bin"
```

Pass this to yt-dlp via `--ffmpeg-location` flag. Never assume ffmpeg is on PATH.

---

## Dependencies

Do not install packages not in `requirements.txt` without asking first. If you determine a new package is needed, state what it is and why before installing it.

PyTorch is already installed with CUDA support. Do not reinstall it. Do not run `pip install torch` — it will overwrite the CUDA build with a CPU build.

To install remaining dependencies:
```bash
pip install -r requirements.txt
```

---

## Running the app

```bash
conda activate subtitle-tool
cd d:\subtitles-tool
python main.py
```

Server runs at: `http://localhost:8000`
Frontend served at: `http://localhost:8000` (FastAPI serves static/index.html)

---

## Phase 1 definition of done

Do not consider Phase 1 complete until ALL of these pass:

- [ ] `python main.py` starts without errors
- [ ] `http://localhost:8000` loads the UI in a browser
- [ ] A valid `.srt` file is generated from an Indian English YouTube URL
- [ ] The `.srt` file has correct timestamps and readable text
- [ ] A Tamil or Telugu YouTube video is attempted and the result is saved (quality not required, completion required)
- [ ] No unhandled exceptions during a normal happy-path run

---

## What NOT to do

- Do not add authentication, login, or user accounts — this is a local dev tool
- Do not use a database — in-memory job store is fine for Phase 1
- Do not make the frontend fancy — functional beats beautiful at this stage
- Do not add Docker, CI/CD, or deployment config — Phase 2 concern
- Do not upgrade or reinstall PyTorch
- Do not use `os.path` — use `pathlib.Path` instead
- Do not suppress the yt-dlp JavaScript runtime warning — it is non-fatal and expected
- Do not load the Whisper model on every request — load once at startup

---

## Language codes for Whisper

| Language | Code |
|---|---|
| Auto-detect | `None` |
| Tamil | `ta` |
| Telugu | `te` |
| Kannada | `kn` |
| Malayalam | `ml` |
| Hindi | `hi` |
| Indian English | `en` |

---

## When something breaks

1. Print the full error traceback — do not swallow exceptions silently
2. Check CUDA availability first: `python -c "import torch; print(torch.cuda.is_available())"`
3. Check ffmpeg: `C:\ffmpeg\bin\ffmpeg.exe -version`
4. Check yt-dlp: `yt-dlp --version`
5. If the model fails to load, check available VRAM with `nvidia-smi`

---

## Project folder structure expected

```
d:\subtitles-tool\
├── CLAUDE.md               ← this file
├── PROJECT_PLAN.md         ← full spec and roadmap
├── requirements.txt
├── main.py
├── pipeline/
│   ├── __init__.py
│   ├── downloader.py
│   ├── transcriber.py
│   └── formatter.py
├── static/
│   └── index.html
└── outputs/                ← gitignored, created automatically
```

Create any missing folders and files as needed. If `outputs/` does not exist, create it programmatically at startup.