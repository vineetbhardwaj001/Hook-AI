from __future__ import annotations
from typing import Any, Optional
from fastapi import HTTPException, status


class HookAIException(Exception):
    """Base exception for Hook AI."""
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


# ── Auth ──────────────────────────────────────────────────────────────────────
class AuthenticationError(HookAIException):
    def __init__(self, message: str = "Authentication failed."):
        super().__init__("AUTHENTICATION_FAILED", message, 401)

class TokenExpiredError(HookAIException):
    def __init__(self):
        super().__init__("TOKEN_EXPIRED", "Token has expired.", 401)

class InsufficientPermissionsError(HookAIException):
    def __init__(self):
        super().__init__("INSUFFICIENT_PERMISSIONS", "You do not have permission to access this resource.", 403)


# ── Video ─────────────────────────────────────────────────────────────────────
class InvalidVideoError(HookAIException):
    def __init__(self, message: str = "The file is not a valid video."):
        super().__init__("INVALID_VIDEO", message, 400)

class VideoTooLargeError(HookAIException):
    def __init__(self, max_mb: int):
        super().__init__("VIDEO_TOO_LARGE", f"Video exceeds the maximum allowed size of {max_mb} MB.", 400)

class VideoTooLongError(HookAIException):
    def __init__(self, max_sec: int):
        super().__init__("VIDEO_TOO_LONG", f"Video exceeds the maximum allowed duration of {max_sec} seconds.", 400)

class InvalidURLError(HookAIException):
    def __init__(self, message: str = "The provided URL is invalid."):
        super().__init__("INVALID_URL", message, 400)

class UnsupportedURLError(HookAIException):
    def __init__(self):
        super().__init__("UNSUPPORTED_URL", "This URL provider is not supported.", 400)

class VideoDownloadFailedError(HookAIException):
    def __init__(self, message: str = "We could not download this video."):
        super().__init__("VIDEO_DOWNLOAD_FAILED", message, 422)


# ── Processing ────────────────────────────────────────────────────────────────
class FFmpegFailedError(HookAIException):
    def __init__(self, detail: str = ""):
        msg = "Media processing failed." + (f" ({detail})" if detail else "")
        super().__init__("FFMPEG_FAILED", msg, 500)

class TranscriptionFailedError(HookAIException):
    def __init__(self):
        super().__init__("TRANSCRIPTION_FAILED", "Speech transcription could not be completed.", 500)

class ModelLoadFailedError(HookAIException):
    def __init__(self, model: str = ""):
        msg = f"AI model could not be loaded." + (f" ({model})" if model else "")
        super().__init__("MODEL_LOAD_FAILED", msg, 500)

class AnalysisFailedError(HookAIException):
    def __init__(self, detail: str = ""):
        msg = "Analysis failed." + (f" ({detail})" if detail else "")
        super().__init__("ANALYSIS_FAILED", msg, 500)

class ReportFailedError(HookAIException):
    def __init__(self):
        super().__init__("REPORT_FAILED", "Report generation failed.", 500)


# ── Credits & Plans ───────────────────────────────────────────────────────────
class InsufficientCreditsError(HookAIException):
    def __init__(self):
        super().__init__("INSUFFICIENT_CREDITS", "You do not have enough credits for this analysis.", 402)

class RateLimitedError(HookAIException):
    def __init__(self):
        super().__init__("RATE_LIMITED", "Too many requests. Please try again later.", 429)


# ── Resource ─────────────────────────────────────────────────────────────────
class NotFoundError(HookAIException):
    def __init__(self, resource: str = "Resource"):
        super().__init__("NOT_FOUND", f"{resource} not found.", 404)

class OwnershipError(HookAIException):
    def __init__(self):
        super().__init__("OWNERSHIP_ERROR", "You do not have access to this resource.", 403)
