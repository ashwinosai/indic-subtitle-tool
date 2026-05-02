"""
transcriber.py — Loads the faster-whisper model and transcribes audio files.

This module does two things:
  1. Loads the AI model once at startup and holds it in GPU memory.
  2. Exposes a transcribe() function that takes an audio file and returns segments.

A "segment" is a dict like:
    {"start": 1.24, "end": 4.80, "text": "Hello and welcome."}

The rest of the app (main.py) calls transcribe() and passes the result to formatter.py.
"""

from pathlib import Path
from faster_whisper import WhisperModel


# ── Model configuration ───────────────────────────────────────────────────────
# These values come directly from the project spec in CLAUDE.md.
# large-v3 is OpenAI's best general-purpose model as of 2024.
MODEL_SIZE = "large-v3"

# Maximum video duration we'll accept. Warn the user but don't hard-fail.
MAX_DURATION_MINUTES = 30


def _detect_device() -> tuple[str, str]:
    """Check whether a CUDA GPU is available and return the right device settings.

    Returns:
        A tuple of (device, compute_type) e.g. ("cuda", "float16") or ("cpu", "int8")

    Why do this at all? So the code works on any machine — not just yours.
    On your RTX 2060 SUPER this will always return cuda/float16.
    """
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            print(f"[transcriber] GPU detected: {gpu_name}")
            print(f"[transcriber] Using device=cuda, compute_type=float16")
            return "cuda", "float16"
        else:
            print("[transcriber] WARNING: CUDA not available. Falling back to CPU.")
            print("[transcriber] Transcription will be much slower on CPU.")
            return "cpu", "int8"
    except ImportError:
        print("[transcriber] WARNING: PyTorch not found. Falling back to CPU.")
        return "cpu", "int8"


def load_model() -> WhisperModel:
    """Load the faster-whisper model into GPU (or CPU) memory.

    This function is called ONCE when the FastAPI server starts.
    The returned model object is stored and reused for every transcription request.

    On first run: faster-whisper will download large-v3 (~3GB) automatically.
    Subsequent runs: loads from local cache in ~/.cache/huggingface/

    Returns:
        A WhisperModel instance ready to transcribe.
    """
    device, compute_type = _detect_device()

    print(f"[transcriber] Loading Whisper {MODEL_SIZE} model...")
    print(f"[transcriber] (First run downloads ~3GB — this is normal)")

    # WhisperModel() loads the model weights into memory.
    # cpu_threads is only used when device="cpu" — ignored on CUDA.
    model = WhisperModel(
        MODEL_SIZE,
        device=device,
        compute_type=compute_type,
        cpu_threads=4,
    )

    print(f"[transcriber] Model loaded successfully.")
    return model


def transcribe(model: WhisperModel, audio_path: Path, language: str | None = None) -> list[dict]:
    """Transcribe an audio file and return a list of timed segments.

    Args:
        model:      The WhisperModel instance returned by load_model().
        audio_path: Path to the audio file (WAV recommended, MP3 also works).
        language:   ISO language code like "ta", "te", "en", or None for auto-detect.
                    See CLAUDE.md for the full language code table.

    Returns:
        A list of segment dicts, each with keys:
            "start" (float) — start time in seconds
            "end"   (float) — end time in seconds
            "text"  (str)   — transcribed text for this segment

    Raises:
        FileNotFoundError: If audio_path does not exist.
        RuntimeError:      If transcription fails unexpectedly.
    """
    # ── Input validation ──────────────────────────────────────────────────────
    audio_path = Path(audio_path)  # ensure it's a Path object even if a string was passed
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"[transcriber] Starting transcription: {audio_path.name}")
    if language:
        print(f"[transcriber] Language hint: {language}")
    else:
        print(f"[transcriber] Language: auto-detect")

    # ── Run transcription ─────────────────────────────────────────────────────
    # model.transcribe() returns a generator of Segment objects + transcription info.
    # We pass vad_filter=True to skip silence and prevent hallucinations.
    # beam_size=5 means the model considers 5 candidate continuations at each step
    # (higher = slightly more accurate, slightly slower — 5 is a good balance).
    segments_generator, info = model.transcribe(
        str(audio_path),            # faster-whisper wants a string path, not a Path object
        language=language,          # None means auto-detect
        beam_size=5,
        vad_filter=True,            # skip silence to prevent hallucinated text
        vad_parameters=dict(
            min_silence_duration_ms=500,  # a gap must be 500ms+ to count as silence
        ),
    )

    # ── Log detected language ─────────────────────────────────────────────────
    detected_lang = info.language
    confidence = round(info.language_probability * 100, 1)
    duration_minutes = round(info.duration / 60, 1)

    print(f"[transcriber] Detected language: {detected_lang} (confidence: {confidence}%)")
    print(f"[transcriber] Audio duration: {duration_minutes} minutes")

    # ── Duration check ────────────────────────────────────────────────────────
    # Warn the user if the video is very long — not an error, just a heads-up.
    if info.duration > MAX_DURATION_MINUTES * 60:
        print(
            f"[transcriber] WARNING: Audio is {duration_minutes} minutes long "
            f"(limit: {MAX_DURATION_MINUTES} min). Transcription may take a while."
        )

    # ── Collect segments ──────────────────────────────────────────────────────
    # segments_generator is lazy — it processes audio chunk by chunk as you iterate.
    # We collect everything into a list so the caller gets a simple, complete result.
    segments = []
    print(f"[transcriber] Processing segments...")

    for segment in segments_generator:
        segments.append({
            "start": segment.start,
            "end":   segment.end,
            "text":  segment.text,
        })
        # Print each segment as it arrives so you can see progress in real time
        print(f"[transcriber]  [{segment.start:.1f}s -> {segment.end:.1f}s] {segment.text.strip()}")

    print(f"[transcriber] Done. {len(segments)} segments transcribed.")
    return segments


# ── Manual test ───────────────────────────────────────────────────────────────
# Run with: python pipeline/transcriber.py <path-to-audio.wav>
# Example:  python pipeline/transcriber.py outputs/test.wav
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pipeline/transcriber.py <path-to-audio.wav>")
        print("Example: python pipeline/transcriber.py outputs/test.wav")
        sys.exit(1)

    audio_file = Path(sys.argv[1])

    # Load the model
    whisper_model = load_model()

    # Transcribe — auto-detect language
    result_segments = transcribe(whisper_model, audio_file, language=None)

    # Print a summary
    print(f"\n=== Result: {len(result_segments)} segments ===")
    for seg in result_segments:
        print(f"  {seg['start']:.2f}s -> {seg['end']:.2f}s : {seg['text'].strip()}")
