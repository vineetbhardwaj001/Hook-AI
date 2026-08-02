"""
Frame extraction and OpenCV visual analysis service.
"""
from __future__ import annotations
import os
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.core.logging import get_logger
from app.services.ffmpeg_service import (
    extract_frames_at_timestamps,
    extract_scene_change_timestamps,
)

logger = get_logger(__name__)


def select_key_timestamps(
    duration: float,
    scene_changes: List[float],
    hook_timestamps: List[float] = None,
    cta_timestamps: List[float] = None,
) -> List[Dict[str, Any]]:
    """
    Intelligently select important frame timestamps without extracting every frame.
    Returns list of {timestamp, reason} dicts.
    """
    selected = []
    seen = set()

    def add(ts: float, reason: str):
        ts = round(ts, 2)
        if 0 <= ts <= duration and ts not in seen:
            seen.add(ts)
            selected.append({"timestamp": ts, "reason": reason})

    # Opening frames (critical for hook analysis)
    add(0.0, "opening")
    add(min(1.0, duration * 0.02), "opening_1s")
    add(min(2.0, duration * 0.05), "opening_2s")
    add(min(3.0, duration * 0.07), "opening_3s")
    add(min(5.0, duration * 0.10), "opening_5s")
    if duration > 10:
        add(min(10.0, duration * 0.15), "opening_10s")

    # Scene changes (up to 15)
    for ts in scene_changes[:15]:
        add(ts, "scene_change")

    # Hook frames
    if hook_timestamps:
        for ts in hook_timestamps[:5]:
            add(ts, "hook_moment")

    # CTA frames
    if cta_timestamps:
        for ts in cta_timestamps[:3]:
            add(ts, "cta_moment")

    # Periodic frames (every 20% of video)
    for pct in [0.2, 0.4, 0.6, 0.8, 1.0]:
        ts = min(duration * pct, duration - 0.1)
        add(ts, "periodic")

    # End frame
    add(max(0, duration - 2.0), "closing")

    return sorted(selected, key=lambda x: x["timestamp"])


def analyze_frames_opencv(frame_paths: List[str]) -> Dict[str, Any]:
    """
    Run OpenCV analysis on extracted frames.
    Returns visual metrics: motion intensity, brightness, scene variety.
    """
    try:
        import cv2
        import numpy as np

        if not frame_paths:
            return _empty_visual_metrics()

        brightness_vals = []
        contrast_vals = []
        prev_gray = None
        motion_scores = []
        similarities = []

        for path in frame_paths:
            if not os.path.exists(path):
                continue
            img = cv2.imread(path)
            if img is None:
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Brightness
            brightness = float(np.mean(gray))
            brightness_vals.append(brightness)

            # Contrast (std of gray values)
            contrast = float(np.std(gray))
            contrast_vals.append(contrast)

            # Motion (frame difference vs prev)
            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                motion = float(np.mean(diff))
                motion_scores.append(motion)
                # Similarity (1 - normalized diff)
                similarity = 1.0 - (motion / 255.0)
                similarities.append(similarity)

            prev_gray = gray

        if not brightness_vals:
            return _empty_visual_metrics()

        avg_brightness = float(np.mean(brightness_vals))
        avg_contrast = float(np.mean(contrast_vals))
        avg_motion = float(np.mean(motion_scores)) if motion_scores else 0.0
        avg_similarity = float(np.mean(similarities)) if similarities else 1.0

        # Visual variation score (0-100): high motion + low similarity = high variation
        visual_variation = round((1.0 - avg_similarity) * 50 + min(50, avg_motion), 1)

        # Visual score based on brightness, contrast, variation
        visual_score = 50.0
        if 80 <= avg_brightness <= 200:
            visual_score += 15  # Well-lit
        if avg_contrast > 40:
            visual_score += 10  # Good contrast
        if visual_variation > 20:
            visual_score += 15  # Dynamic visuals
        if avg_motion > 5:
            visual_score += 10  # Active/engaging

        return {
            "avg_brightness": round(avg_brightness, 1),
            "avg_contrast": round(avg_contrast, 1),
            "avg_motion": round(avg_motion, 1),
            "visual_variation": visual_variation,
            "avg_frame_similarity": round(avg_similarity, 4),
            "visual_score": round(min(100.0, visual_score), 1),
            "frames_analyzed": len(brightness_vals),
        }

    except ImportError:
        logger.warning("OpenCV not installed — skipping frame analysis.")
        return _empty_visual_metrics()
    except Exception as e:
        logger.warning(f"OpenCV frame analysis failed: {e}")
        return _empty_visual_metrics()


def _empty_visual_metrics() -> Dict[str, Any]:
    return {
        "avg_brightness": 128.0,
        "avg_contrast": 40.0,
        "avg_motion": 10.0,
        "visual_variation": 30.0,
        "avg_frame_similarity": 0.7,
        "visual_score": 50.0,
        "frames_analyzed": 0,
    }


def extract_key_frames(
    video_path: str,
    output_dir: str,
    duration: float,
    hook_starts: List[float] = None,
    cta_starts: List[float] = None,
) -> List[Dict[str, Any]]:
    """
    Extract key frames from video. Returns list of frame metadata dicts.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Get scene changes
    try:
        scene_changes = extract_scene_change_timestamps(video_path, threshold=0.3)
    except Exception as e:
        logger.warning(f"Scene change detection failed: {e}")
        scene_changes = []

    # Select timestamps
    timestamp_info = select_key_timestamps(
        duration=duration,
        scene_changes=scene_changes,
        hook_timestamps=hook_starts,
        cta_timestamps=cta_starts,
    )
    timestamps = [t["timestamp"] for t in timestamp_info]
    reason_map = {t["timestamp"]: t["reason"] for t in timestamp_info}

    # Extract frames
    frame_paths = extract_frames_at_timestamps(video_path, timestamps, output_dir)

    frames = []
    for i, path in enumerate(frame_paths):
        ts = timestamps[i] if i < len(timestamps) else 0
        frame_id = str(uuid.uuid4())[:8]
        frames.append({
            "frame_id": frame_id,
            "timestamp": ts,
            "reason": reason_map.get(round(ts, 2), "sampled"),
            "path": path,
            "public_url": f"/storage/{os.path.relpath(path, 'storage').replace(os.sep, '/')}",
        })

    return frames
