"""
downloader.py — Downloads audio from a YouTube URL using yt-dlp + ffmpeg.

Responsibilities:
  - Accept a YouTube URL
  - Use yt-dlp to download the best available audio stream
  - Convert it to WAV using ffmpeg (for best Whisper compatibility)
  - Return the path to the downloaded WAV file
  - Handle errors: invalid URL, private video, unavailable video, too long

ffmpeg is NOT on the system PATH on this machine.
It lives at C:\\ffmpeg\\bin and must be passed explicitly to yt-dlp.
"""

from pathlib import Path
import yt_dlp


# ── Configuration ─────────────────────────────────────────────────────────────
FFMPEG_LOCATION = r"C:\ffmpeg\bin"
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"

# Warn the user if the video is longer than this (in seconds)
MAX_DURATION_SECONDS = 30 * 60  # 30 minutes


def download_audio(url: str, job_id: str) -> Path:
    """Download audio from a YouTube URL and return the path to the WAV file.

    This is the main function the rest of the app calls.
    It fetches metadata AND downloads in a single yt-dlp call — no double call,
    no doubled warning spam.

    Args:
        url:    A valid YouTube video URL (plain video or playlist/mix URL — we
                always extract only the single video the URL points to).
        job_id: Unique identifier for this job — used to name the output file
                so multiple concurrent jobs don't overwrite each other.

    Returns:
        A Path object pointing to the downloaded WAV file.

    Raises:
        ValueError:        If the URL is invalid or the video is unavailable/private.
        FileNotFoundError: If ffmpeg is not found at FFMPEG_LOCATION.
        RuntimeError:      If the download fails for any other reason.
    """
    # ── Check ffmpeg exists ───────────────────────────────────────────────────
    ffmpeg_exe = Path(FFMPEG_LOCATION) / "ffmpeg.exe"
    if not ffmpeg_exe.exists():
        raise FileNotFoundError(
            f"ffmpeg not found at {ffmpeg_exe}. "
            f"Check that ffmpeg is installed at C:\\ffmpeg\\bin"
        )

    # ── Ensure output directory exists ────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Single yt-dlp call: fetch info + download in one shot ─────────────────
    # Previously we called yt-dlp twice (once for info, once for download).
    # Using extract_info(download=True) does both at once — halves the warning spam.
    #
    # noplaylist=True is critical: if the user pastes a URL that includes
    # &list=... or &start_radio=1 (YouTube Mix/playlist URLs), yt-dlp would try
    # to enumerate every video in the list. noplaylist=True forces it to only
    # download the single video the URL points to.
    output_template = str(OUTPUT_DIR / f"{job_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }
        ],
        "ffmpeg_location": FFMPEG_LOCATION,
        "quiet": True,
        "no_warnings": False,
        "noplaylist": True,   # KEY FIX: ignore playlist/mix params, download single video only
    }

    print(f"[downloader] Fetching info and downloading: {url}")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info with download=True fetches metadata AND downloads in one pass
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise ValueError(f"Invalid or unavailable YouTube URL.\nDetails: {e}")

    # ── Log what we got ───────────────────────────────────────────────────────
    title    = info.get("title", "Unknown")
    duration = info.get("duration") or 0
    uploader = info.get("uploader", "Unknown")
    duration_minutes = round(duration / 60, 1)

    print(f"[downloader] Title:    {title}")
    print(f"[downloader] Uploader: {uploader}")
    print(f"[downloader] Duration: {duration_minutes} minutes")

    if duration > MAX_DURATION_SECONDS:
        print(
            f"[downloader] WARNING: This video is {duration_minutes} minutes long "
            f"(recommended max: {MAX_DURATION_SECONDS // 60} min). "
            f"Transcription will work but may take a long time."
        )

    # ── Verify output file exists ─────────────────────────────────────────────
    # yt-dlp's postprocessor renames the file to .wav after conversion
    wav_path = OUTPUT_DIR / f"{job_id}.wav"
    if not wav_path.exists():
        raise RuntimeError(
            f"Download appeared to succeed but WAV file not found at {wav_path}. "
            f"Check that ffmpeg is working correctly."
        )

    print(f"[downloader] Audio saved: {wav_path}")
    return wav_path


# ── Manual test ───────────────────────────────────────────────────────────────
# Run with: python pipeline/downloader.py <youtube-url>
# Example:  python pipeline/downloader.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pipeline/downloader.py <youtube-url>")
        print('Example: python pipeline/downloader.py "https://youtu.be/dQw4w9WgXcQ"')
        sys.exit(1)

    youtube_url = sys.argv[1]
    test_job_id = "downloader-test-001"

    print(f"Testing downloader with URL: {youtube_url}\n")
    audio_path = download_audio(youtube_url, job_id=test_job_id)
    print(f"\nSuccess! Audio file at: {audio_path}")
    print(f"File size: {audio_path.stat().st_size / (1024*1024):.1f} MB")
