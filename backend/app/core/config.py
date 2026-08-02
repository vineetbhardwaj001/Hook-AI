from __future__ import annotations
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./hookai.db"
    mongo_uri: str = "mongodb+srv://bhar-990:wB7PcnEz8sB9t4jZ@cluster0.tiyilrz.mongodb.net/hook?appName=Cluster0"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # CORS — stored as comma-separated string to avoid pydantic-settings JSON parsing
    cors_origins_str: str = "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:8080"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.cors_origins_str.split(",") if o.strip()]

    # Video limits
    max_video_size_mb: int = 500
    max_video_duration_seconds: int = 3600

    # Storage
    storage_provider: str = "local"
    storage_local_base: str = "storage"
    s3_bucket: str = ""
    s3_endpoint: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # AI Device & Profile
    hook_ai_device: str = "auto"
    hook_ai_profile: str = "balanced"

    # Models
    whisper_model: str = "openai/whisper-large-v3-turbo"
    whisper_model_size: str = "base"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    emotion_model: str = "j-hartmann/emotion-english-distilroberta-base"
    vision_model: str = "Qwen/Qwen3-VL-4B-Instruct"
    text_generation_model: str = "microsoft/Phi-3-mini-4k-instruct"

    # FFmpeg
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Cleanup
    temp_file_retention_hours: int = 24

    # Score weights
    score_weight_hook: float = 0.25
    score_weight_cta: float = 0.15
    score_weight_tone: float = 0.10
    score_weight_visual: float = 0.15
    score_weight_pacing: float = 0.10
    score_weight_clarity: float = 0.10
    score_weight_engagement: float = 0.15

    # Rate limits
    rate_limit_login: str = "5/minute"
    rate_limit_signup: str = "3/minute"
    rate_limit_analysis: str = "10/hour"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def score_weights(self) -> dict:
        return {
            "hook": self.score_weight_hook,
            "cta": self.score_weight_cta,
            "tone": self.score_weight_tone,
            "visual": self.score_weight_visual,
            "pacing": self.score_weight_pacing,
            "clarity": self.score_weight_clarity,
            "engagement": self.score_weight_engagement,
        }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
