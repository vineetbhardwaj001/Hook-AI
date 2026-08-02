"""
Audio Analysis Service — librosa-based audio signal analysis.
"""
from __future__ import annotations
from typing import Dict, Any, List
import logging
from app.core.logging import get_logger

logger = get_logger(__name__)






def analyze_audio(audio_path: str, transcript_segments: List[Dict] = None, duration: float = 0) -> Dict[str, Any]:
    """
    Analyze audio for silence, energy, pacing signals.
    Returns audio analysis dict.
    """
    try:
        import librosa
        import numpy as np

        y, sr = librosa.load(audio_path, sr=None, mono=True)
        actual_duration = librosa.get_duration(y=y, sr=sr)

        # RMS energy
        frame_length = 2048
        hop_length = 512
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        rms_db = librosa.amplitude_to_db(rms, ref=np.max)

        # Silence detection (frames where energy < -40dB)
        silence_threshold_db = -40
        silent_frames = rms_db < silence_threshold_db
        silence_ratio = float(np.mean(silent_frames))

        # Detect silence regions
        frame_times = librosa.frames_to_time(
            np.arange(len(rms)), sr=sr, hop_length=hop_length
        )
        silence_regions = _detect_silence_regions(silent_frames, frame_times)

        # Long pauses (silence > 1.5s)
        long_pauses = [r for r in silence_regions if r["duration"] > 1.5]

        # Energy variation (std of RMS in non-silent frames)
        active_rms = rms[~silent_frames]
        energy_variation = float(np.std(active_rms)) if len(active_rms) > 0 else 0.0

        # Volume variation (normalize)
        volume_variation = round(min(1.0, energy_variation / (np.mean(active_rms) + 1e-9)), 4) if len(active_rms) > 0 else 0.0

        # Speech activity ratio
        speech_ratio = 1.0 - silence_ratio

        # Tempo-like pacing from onset strength (Version-safe extraction)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        
        try:
            # Librosa 0.10+
            tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)
        except AttributeError:
            # Fallback for older Librosa versions
            tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)

        # Handle array vs scalar return type
        if hasattr(tempo, "__len__"):
            estimated_tempo = float(tempo[0])
        else:
            estimated_tempo = float(tempo)

        # Peak energy moments
        peak_energy_idx = np.argsort(rms)[-5:][::-1]
        peak_moments = [round(float(frame_times[min(i, len(frame_times)-1)]), 2) for i in peak_energy_idx]

        return {
            "duration": round(actual_duration, 2),
            "silence_ratio": round(silence_ratio, 4),
            "speech_ratio": round(speech_ratio, 4),
            "long_pauses": long_pauses[:10],
            "energy_variation": round(energy_variation, 4),
            "volume_variation": volume_variation,
            "peak_energy_moments": peak_moments,
            "estimated_tempo": round(estimated_tempo, 1),
        }

    except ImportError:
        logger.warning("librosa not installed — using basic audio analysis.")
        return _basic_audio_analysis(transcript_segments, duration)
    except Exception as e:
        logger.warning(f"Audio analysis failed: {e}")
        return _basic_audio_analysis(transcript_segments, duration)

def _detect_silence_regions(silent_frames, frame_times) -> List[Dict]:
    regions = []
    in_silence = False
    start_time = 0.0

    for i, is_silent in enumerate(silent_frames):
        t = frame_times[i] if i < len(frame_times) else 0
        if is_silent and not in_silence:
            in_silence = True
            start_time = t
        elif not is_silent and in_silence:
            in_silence = False
            dur = t - start_time
            if dur >= 0.3:  # Only record silences >= 300ms
                regions.append({"start": round(start_time, 2), "end": round(t, 2), "duration": round(dur, 2)})

    return regions


def _basic_audio_analysis(segments: List[Dict] = None, duration: float = 0) -> Dict[str, Any]:
    """Fallback when librosa is not available."""
    if not segments:
        return {
            "duration": duration,
            "silence_ratio": 0.2,
            "speech_ratio": 0.8,
            "long_pauses": [],
            "energy_variation": 0.3,
            "volume_variation": 0.3,
            "peak_energy_moments": [],
            "estimated_tempo": 120.0,
        }

    # Estimate from transcript gaps
    gaps = []
    for i in range(1, len(segments)):
        gap_start = segments[i-1].get("end", 0)
        gap_end = segments[i].get("start", 0)
        gap_dur = gap_end - gap_start
        if gap_dur > 0.3:
            gaps.append({"start": round(gap_start, 2), "end": round(gap_end, 2), "duration": round(gap_dur, 2)})

    total_gap = sum(g["duration"] for g in gaps)
    silence_ratio = round(total_gap / duration, 4) if duration > 0 else 0.1
    long_pauses = [g for g in gaps if g["duration"] > 1.5]

    return {
        "duration": duration,
        "silence_ratio": silence_ratio,
        "speech_ratio": round(1.0 - silence_ratio, 4),
        "long_pauses": long_pauses[:10],
        "energy_variation": 0.3,
        "volume_variation": 0.3,
        "peak_energy_moments": [],
        "estimated_tempo": 120.0,
    }
