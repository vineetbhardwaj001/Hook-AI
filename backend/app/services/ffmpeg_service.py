"""
FFmpeg/ffprobe media processing service.
All subprocess calls use argument arrays — never shell=True with user data.
"""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from app.core.config import get_settings
from app.core.exceptions import FFmpegFailedError, InvalidVideoError
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _run(args: list, timeout: int = 300) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result
    except subprocess.TimeoutExpired:
        raise FFmpegFailedError("Processing timed out.")
    except FileNotFoundError:
        raise FFmpegFailedError(f"Binary not found: {args[0]}")


def probe_media(video_path: str) -> Dict[str, Any]:
    """Run ffprobe and return parsed metadata."""
    args = [
        settings.ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]
    result = _run(args, timeout=60)
    if result.returncode != 0:
        raise InvalidVideoError(f"ffprobe failed: {result.stderr[:200]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise InvalidVideoError("Could not parse media metadata.")


def get_video_info(video_path: str) -> Dict[str, Any]:
    """Return cleaned video info dict."""
    meta = probe_media(video_path)
    fmt = meta.get("format", {})
    streams = meta.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = float(fmt.get("duration") or 0)
    width = int(video_stream.get("width") or 0) if video_stream else 0
    height = int(video_stream.get("height") or 0) if video_stream else 0

    fps = 0.0
    if video_stream:
        fps_str = video_stream.get("r_frame_rate", "0/1")
        try:
            num, den = fps_str.split("/")
            fps = round(float(num) / float(den), 2) if float(den) != 0 else 0.0
        except Exception:
            fps = 0.0

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "video_codec": video_stream.get("codec_name") if video_stream else None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "bitrate": int(fmt.get("bit_rate") or 0),
        "size_bytes": int(fmt.get("size") or 0),
        "has_audio": audio_stream is not None,
        "has_video": video_stream is not None,
    }


def extract_audio(video_path: str, output_path: str) -> str:
    """Extract mono 16kHz WAV from video. Returns output path."""
    args = [
        settings.ffmpeg_path,
        "-i", video_path,
        "-vn",                    # no video
        "-acodec", "pcm_s16le",  # 16-bit PCM WAV
        "-ar", "16000",           # 16kHz (whisper optimal)
        "-ac", "1",               # mono
        "-y",                     # overwrite
        output_path,
    ]
    result = _run(args, timeout=300)
    if result.returncode != 0:
        raise FFmpegFailedError(f"Audio extraction failed: {result.stderr[:200]}")
    return output_path


def extract_frames_at_timestamps(video_path: str, timestamps: list[float], output_dir: str) -> list[str]:
    """Extract specific frames at given timestamps. Returns list of output paths."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    paths = []
    for i, ts in enumerate(timestamps):
        out = os.path.join(output_dir, f"frame_{i:04d}_{ts:.2f}.jpg")
        args = [
            settings.ffmpeg_path,
            "-ss", str(ts),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            "-y",
            out,
        ]
        result = _run(args, timeout=30)
        if result.returncode == 0 and os.path.exists(out):
            paths.append(out)
    return paths


def extract_scene_change_timestamps(video_path: str, threshold: float = 0.3) -> list[float]:
    """Use ffprobe scene detection to get scene change timestamps."""
    args = [
        settings.ffmpeg_path,
        "-i", video_path,
        "-filter:v", f"select=gt(scene\\,{threshold}),showinfo",
        "-f", "null",
        "-",
    ]
    result = _run(args, timeout=120)
    timestamps = []
    for line in (result.stdout + result.stderr).split("\n"):
        if "pts_time:" in line:
            try:
                part = line.split("pts_time:")[1].split()[0]
                timestamps.append(float(part))
            except (IndexError, ValueError):
                pass
    return sorted(set(timestamps))


def get_thumbnail(video_path: str, output_path: str, timestamp: float = 0.0) -> str:
    """Extract a thumbnail image at given timestamp."""
    args = [
        settings.ffmpeg_path,
        "-ss", str(timestamp),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "3",
        "-y",
        output_path,
    ]
    result = _run(args, timeout=30)
    if result.returncode != 0:
        return ""
    return output_path
