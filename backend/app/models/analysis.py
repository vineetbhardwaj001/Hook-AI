from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String, Boolean, DateTime, Integer, Float, Text, ForeignKey, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.user import utcnow


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(100), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    analysis_type: Mapped[str] = mapped_column(String(50), default="full")
    language: Mapped[str] = mapped_column(String(10), default="en")
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    notify_when_ready: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_options: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    credits_used: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="analyses")
    video_asset: Mapped[VideoAsset] = relationship(back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    transcript: Mapped[Transcript] = relationship(back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    hook_result: Mapped[HookResult] = relationship(back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    cta_result: Mapped[CTAResult] = relationship(back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    tone_result: Mapped[ToneResult] = relationship(back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    visual_result: Mapped[VisualResult] = relationship(back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    pacing_result: Mapped[PacingResult] = relationship(back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    engagement_result: Mapped[EngagementResult] = relationship(back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    analysis_score: Mapped[AnalysisScore] = relationship(back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    generated_script: Mapped[GeneratedScript] = relationship(back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    report: Mapped[Report] = relationship(back_populates="analysis", uselist=False, cascade="all, delete-orphan")


class VideoAsset(Base):
    __tablename__ = "video_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    source: Mapped[str] = mapped_column(String(20), default="upload")  # upload, youtube, url
    original_url: Mapped[str] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=True)
    public_url: Mapped[str] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str] = mapped_column(Text, nullable=True)
    duration: Mapped[float] = mapped_column(Float, nullable=True)
    width: Mapped[int] = mapped_column(Integer, nullable=True)
    height: Mapped[int] = mapped_column(Integer, nullable=True)
    fps: Mapped[float] = mapped_column(Float, nullable=True)
    video_codec: Mapped[str] = mapped_column(String(50), nullable=True)
    audio_codec: Mapped[str] = mapped_column(String(50), nullable=True)
    bitrate: Mapped[int] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=True)
    has_audio: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="video_asset")


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    language: Mapped[str] = mapped_column(String(10), nullable=True)
    full_text: Mapped[str] = mapped_column(Text, nullable=True, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    words_per_minute: Mapped[float] = mapped_column(Float, nullable=True)
    segments: Mapped[list] = mapped_column(JSON, default=list)  # [{id, start, end, text}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="transcript")


class HookResult(Base):
    __tablename__ = "hook_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    hook_score: Mapped[float] = mapped_column(Float, default=0.0)
    best_hook: Mapped[dict] = mapped_column(JSON, default=dict)
    hooks: Mapped[list] = mapped_column(JSON, default=list)
    opening_analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="hook_result")


class CTAResult(Base):
    __tablename__ = "cta_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    cta_score: Mapped[float] = mapped_column(Float, default=0.0)
    ctas: Mapped[list] = mapped_column(JSON, default=list)
    has_cta: Mapped[bool] = mapped_column(Boolean, default=False)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="cta_result")


class ToneResult(Base):
    __tablename__ = "tone_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    primary_tone: Mapped[str] = mapped_column(String(100), nullable=True)
    sentiment: Mapped[str] = mapped_column(String(50), nullable=True)
    emotions: Mapped[dict] = mapped_column(JSON, default=dict)
    energy_score: Mapped[float] = mapped_column(Float, default=0.0)
    clarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    observations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="tone_result")


class VisualResult(Base):
    __tablename__ = "visual_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    visual_score: Mapped[float] = mapped_column(Float, default=0.0)
    key_moments: Mapped[list] = mapped_column(JSON, default=list)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="visual_result")


class PacingResult(Base):
    __tablename__ = "pacing_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    pacing_score: Mapped[float] = mapped_column(Float, default=0.0)
    words_per_minute: Mapped[float] = mapped_column(Float, nullable=True)
    silence_ratio: Mapped[float] = mapped_column(Float, nullable=True)
    scene_change_frequency: Mapped[float] = mapped_column(Float, nullable=True)
    timeline_events: Mapped[list] = mapped_column(JSON, default=list)
    audio_signals: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="pacing_result")


class EngagementResult(Base):
    __tablename__ = "engagement_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0)
    contributing_signals: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="engagement_result")


class AnalysisScore(Base):
    __tablename__ = "analysis_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    overall: Mapped[float] = mapped_column(Float, default=0.0)
    hook: Mapped[float] = mapped_column(Float, default=0.0)
    cta: Mapped[float] = mapped_column(Float, default=0.0)
    tone: Mapped[float] = mapped_column(Float, default=0.0)
    visual: Mapped[float] = mapped_column(Float, default=0.0)
    pacing: Mapped[float] = mapped_column(Float, default=0.0)
    clarity: Mapped[float] = mapped_column(Float, default=0.0)
    engagement: Mapped[float] = mapped_column(Float, default=0.0)
    rating: Mapped[str] = mapped_column(String(50), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="analysis_score")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    category: Mapped[str] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[float] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="recommendations")


class GeneratedScript(Base):
    __tablename__ = "generated_scripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    hook: Mapped[str] = mapped_column(Text, nullable=True)
    sections: Mapped[list] = mapped_column(JSON, default=list)
    full_script: Mapped[str] = mapped_column(Text, nullable=True)
    estimated_duration: Mapped[int] = mapped_column(Integer, nullable=True)
    changes: Mapped[list] = mapped_column(JSON, default=list)
    platform: Mapped[str] = mapped_column(String(50), nullable=True)
    tone: Mapped[str] = mapped_column(String(50), nullable=True)
    audience: Mapped[str] = mapped_column(String(200), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="generated_script")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    xlsx_path: Mapped[str] = mapped_column(Text, nullable=True)
    xlsx_url: Mapped[str] = mapped_column(Text, nullable=True)
    json_path: Mapped[str] = mapped_column(Text, nullable=True)
    xlsx_available: Mapped[bool] = mapped_column(Boolean, default=False)
    json_available: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="report")
