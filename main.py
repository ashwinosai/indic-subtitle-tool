"""
main.py — FastAPI web server. The orchestrator that wires everything together.

Endpoints:
  POST /transcribe        → start a job, return job_id immediately
  GET  /status/{job_id}   → check if job is done
  GET  /download/{job_id} → download the finished subtitle file
  GET  /                  → serve the frontend (index.html)

The model is loaded ONCE at startup and reused for every request.
Transcription runs in a background thread so the HTTP request returns immediately.
"""

import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pipeline.downloader import download_audio
from pipeline.formatter import write_subtitle_file
from pipeline.transcriber import load_model, transcribe

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="Indic Subtitle Tool")

# CORS — allows the browser frontend to talk to this server.
# In Phase 1 we allow all origins ("*") since this is a local dev tool.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global state ──────────────────────────────────────────────────────────────
# The model is loaded once here. Every transcription request uses this same object.
# Loading takes ~10 seconds and uses ~4GB of VRAM — we do it once, not per request.
print("[main] Loading Whisper model at startup...")
whisper_model = load_model()
print("[main] Model ready. Server starting.")

# In-memory job store. Structure per job:
# {
#   "status": "processing" | "done" | "error",
#   "file":   Path object (only when status == "done"),
#   "format": "srt" or "vtt",
#   "error":  str (only when status == "error"),
# }
jobs: dict[str, dict] = {}

# ── Request/Response models ───────────────────────────────────────────────────
# Pydantic models define exactly what JSON shape we expect from the client.
# FastAPI validates incoming requests against these automatically.

class TranscribeRequest(BaseModel):
    url: str
    language: str = "auto"   # default to auto-detect
    format: str = "srt"      # default to SRT


class TranscribeResponse(BaseModel):
    job_id: str
    status: str


class StatusResponse(BaseModel):
    status: str
    message: str | None = None   # human-readable progress text shown in the UI
    download_url: str | None = None
    error: str | None = None


# ── Background worker ─────────────────────────────────────────────────────────

def run_pipeline(job_id: str, url: str, language: str | None, fmt: str) -> None:
    """Run the full download → transcribe → format pipeline in a background thread.

    This function is called in a new thread for each request so the HTTP
    response can return immediately while work happens in the background.

    Args:
        job_id:   Unique ID for this job.
        url:      YouTube URL to process.
        language: ISO language code or None for auto-detect.
        fmt:      "srt" or "vtt".
    """
    audio_path = None  # track so we can clean up even if an error occurs

    try:
        # Step 1 — Download audio from YouTube
        print(f"[job:{job_id}] Step 1/3 — Downloading audio")
        jobs[job_id]["message"] = "Downloading audio from YouTube..."
        audio_path = download_audio(url, job_id)

        # Step 2 — Transcribe with Whisper
        print(f"[job:{job_id}] Step 2/3 — Transcribing")
        jobs[job_id]["message"] = "Transcribing with Whisper AI (this takes 1-3 minutes)..."
        segments = transcribe(whisper_model, audio_path, language=language)

        # Handle the case where no speech was found in the audio
        if len(segments) == 0:
            raise RuntimeError(
                "No speech detected in this video. "
                "This usually means the video is music-only, or the language hint doesn't match. "
                "Try selecting 'Auto-detect' language, or use a video that contains spoken words."
            )

        # Step 3 — Write subtitle file
        print(f"[job:{job_id}] Step 3/3 — Writing {fmt.upper()} file")
        jobs[job_id]["message"] = "Writing subtitle file..."
        output_file = write_subtitle_file(segments, job_id, fmt)

        # Mark job as done
        jobs[job_id]["status"] = "done"
        jobs[job_id]["message"] = f"Done! {len(segments)} subtitle segments generated."
        jobs[job_id]["file"] = output_file
        print(f"[job:{job_id}] Complete -> {output_file}")

    except Exception as e:
        # Catch everything so one bad job doesn't crash the server
        import traceback
        error_msg = str(e)
        print(f"[job:{job_id}] ERROR: {error_msg}")
        traceback.print_exc()
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = error_msg

    finally:
        # Always clean up the audio file — we don't need it after transcription
        if audio_path and Path(audio_path).exists():
            Path(audio_path).unlink()
            print(f"[job:{job_id}] Cleaned up audio file")


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.post("/transcribe", response_model=TranscribeResponse)
def start_transcription(request: TranscribeRequest):
    """Start a transcription job. Returns immediately with a job_id.

    The actual work happens in a background thread.
    Poll /status/{job_id} to check progress.
    """
    # Normalise language — "auto" means pass None to Whisper (auto-detect)
    language = None if request.language == "auto" else request.language

    # Validate format
    if request.format not in ("srt", "vtt"):
        raise HTTPException(status_code=400, detail="format must be 'srt' or 'vtt'")

    # Create a unique ID for this job
    job_id = str(uuid.uuid4())

    # Register the job in our store immediately
    jobs[job_id] = {"status": "processing", "format": request.format, "message": "Starting..."}

    # Start background thread — daemon=True means it won't block server shutdown
    thread = threading.Thread(
        target=run_pipeline,
        args=(job_id, request.url, language, request.format),
        daemon=True,
    )
    thread.start()

    print(f"[main] Started job {job_id} for URL: {request.url}")
    return TranscribeResponse(job_id=job_id, status="processing")


@app.get("/status/{job_id}", response_model=StatusResponse)
def get_status(job_id: str):
    """Check the status of a transcription job.

    Returns:
        status: "processing" | "done" | "error"
        download_url: set when status is "done"
        error: set when status is "error"
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    job = jobs[job_id]
    status = job["status"]

    if status == "done":
        return StatusResponse(
            status="done",
            message=job.get("message"),
            download_url=f"/download/{job_id}",
        )
    elif status == "error":
        return StatusResponse(
            status="error",
            error=job.get("error", "Unknown error"),
        )
    else:
        return StatusResponse(
            status="processing",
            message=job.get("message", "Processing..."),
        )


@app.get("/download/{job_id}")
def download_file(job_id: str):
    """Download the finished subtitle file.

    Returns the file as an attachment so the browser triggers a Save dialog.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    job = jobs[job_id]

    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job is not complete yet")

    file_path: Path = job["file"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Output file missing from disk")

    fmt = job["format"]
    # FileResponse sends the file and sets Content-Disposition: attachment
    # so the browser downloads it instead of displaying it
    return FileResponse(
        path=file_path,
        filename=f"subtitles.{fmt}",
        media_type="text/plain",
    )


# ── Serve frontend ────────────────────────────────────────────────────────────
# Serve index.html at the root URL.
# This must be registered AFTER the API routes so /transcribe etc. take priority.
app.mount("/", StaticFiles(directory="static", html=True), name="static")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0" makes the server accessible on your local network,
    # not just from localhost. Useful if you want to test from your phone.
    uvicorn.run(app, host="0.0.0.0", port=8000)
