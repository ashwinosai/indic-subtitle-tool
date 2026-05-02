"""
formatter.py — Converts Whisper transcription segments into .srt or .vtt subtitle files.

A "segment" from Whisper looks like:
    { "start": 1.24, "end": 4.80, "text": "Hello and welcome." }

Start and end are floating-point seconds (e.g. 1.24 = 1 second and 240 milliseconds).
Our job here is to turn those numbers into the proper timestamp strings that
subtitle players understand, then assemble the file and write it to disk.
"""

from pathlib import Path


# The outputs directory sits next to this project's root, not inside pipeline/.
# Path(__file__) is the full path to THIS file (formatter.py).
# .parent gives us the pipeline/ folder.
# .parent again gives us the project root (subtitles-tool/).
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


def _seconds_to_srt_timestamp(seconds: float) -> str:
    """Convert a float number of seconds to SRT timestamp format: HH:MM:SS,mmm

    Example: 3661.5 → '01:01:01,500'

    SRT uses a comma before milliseconds. This is different from VTT which uses a dot.
    The distinction matters — subtitle players are strict about this format.
    """
    # Split seconds into whole seconds and the leftover milliseconds
    total_ms = int(round(seconds * 1000))  # convert to milliseconds, round to nearest int
    ms = total_ms % 1000                    # remainder after pulling out whole seconds
    total_seconds = total_ms // 1000        # whole seconds only

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    # :02d means "format as integer, pad with zeros to width 2"
    # :03d means "format as integer, pad with zeros to width 3" (for milliseconds)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _seconds_to_vtt_timestamp(seconds: float) -> str:
    """Convert a float number of seconds to VTT timestamp format: HH:MM:SS.mmm

    VTT is identical to SRT timestamps except it uses a dot before milliseconds.
    Example: 3661.5 → '01:01:01.500'
    """
    # Reuse the SRT function and just swap the comma for a dot
    return _seconds_to_srt_timestamp(seconds).replace(",", ".")


def generate_srt(segments: list[dict]) -> str:
    """Build a complete SRT file as a string from a list of Whisper segments.

    Args:
        segments: List of dicts, each with keys: 'start' (float), 'end' (float), 'text' (str)

    Returns:
        A string containing the full SRT file content, ready to write to disk.
    """
    lines = []

    for index, segment in enumerate(segments, start=1):
        start_ts = _seconds_to_srt_timestamp(segment["start"])
        end_ts = _seconds_to_srt_timestamp(segment["end"])
        text = segment["text"].strip()  # remove leading/trailing whitespace

        # Each SRT block: sequence number, timestamp line, text, blank line
        lines.append(str(index))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append("")  # blank line separator between blocks

    return "\n".join(lines)


def generate_vtt(segments: list[dict]) -> str:
    """Build a complete VTT file as a string from a list of Whisper segments.

    VTT (WebVTT) is the format used natively by HTML5 <video> elements.
    It starts with the header line 'WEBVTT', then works like SRT but without
    sequence numbers and using dots instead of commas in timestamps.

    Args:
        segments: List of dicts, each with keys: 'start' (float), 'end' (float), 'text' (str)

    Returns:
        A string containing the full VTT file content, ready to write to disk.
    """
    lines = ["WEBVTT", ""]  # VTT files MUST start with "WEBVTT" on the first line

    for segment in segments:
        start_ts = _seconds_to_vtt_timestamp(segment["start"])
        end_ts = _seconds_to_vtt_timestamp(segment["end"])
        text = segment["text"].strip()

        # VTT blocks: timestamp line, text, blank line (no sequence number required)
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def write_subtitle_file(segments: list[dict], job_id: str, fmt: str) -> Path:
    """Write subtitle content to a file in the outputs/ directory.

    This is the main function that the rest of the app will call.
    It delegates to generate_srt() or generate_vtt(), then writes the result to disk.

    Args:
        segments: List of segment dicts from the transcriber.
        job_id:   Unique identifier for this transcription job (used as the filename).
        fmt:      Either "srt" or "vtt".

    Returns:
        A Path object pointing to the written file.

    Raises:
        ValueError: If fmt is not "srt" or "vtt".
        FileNotFoundError: If outputs/ directory cannot be created.
    """
    fmt = fmt.lower().strip()
    if fmt not in ("srt", "vtt"):
        raise ValueError(f"Unsupported format '{fmt}'. Choose 'srt' or 'vtt'.")

    # Ensure the outputs directory exists. mkdir(parents=True, exist_ok=True) means:
    # - parents=True  → create any missing parent folders too
    # - exist_ok=True → don't raise an error if the folder already exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    content = generate_srt(segments) if fmt == "srt" else generate_vtt(segments)

    output_path = OUTPUT_DIR / f"{job_id}.{fmt}"
    output_path.write_text(content, encoding="utf-8")

    print(f"[formatter] Written: {output_path}")
    return output_path


# ── Manual test ──────────────────────────────────────────────────────────────
# Run this file directly to verify formatting works without needing any other
# part of the project: python pipeline/formatter.py
if __name__ == "__main__":
    # Fake segments — exactly what faster-whisper will produce later
    test_segments = [
        {"start": 0.0,  "end": 3.5,  "text": "Welcome to this video."},
        {"start": 3.8,  "end": 7.2,  "text": "Today we are building a subtitle tool."},
        {"start": 7.5,  "end": 12.0, "text": "Let us start with the formatter module."},
    ]

    print("=== SRT Output ===")
    print(generate_srt(test_segments))

    print("=== VTT Output ===")
    print(generate_vtt(test_segments))

    print("=== Writing files to outputs/ ===")
    srt_path = write_subtitle_file(test_segments, job_id="test-job-001", fmt="srt")
    vtt_path = write_subtitle_file(test_segments, job_id="test-job-001", fmt="vtt")

    print(f"SRT file: {srt_path}")
    print(f"VTT file: {vtt_path}")
    print("\nDone. Check the outputs/ folder.")
