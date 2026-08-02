from __future__ import annotations
from typing import Optional, List, Any
from pydantic import BaseModel


class AnalysisCreateRequest(BaseModel):
    video_url: Optional[str] = None
    analysis_type: str = "full"
    language: str = "en"
    category: Optional[str] = None
    notify_when_ready: bool = True
    custom_options: Optional[dict] = None


class AnalysisCreateResponse(BaseModel):
    analysis_id: str
    job_id: str
    status: str
    message: str


class AnalysisListItem(BaseModel):
    id: str
    status: str
    stage: str
    progress: int
    analysis_type: str
    video_title: Optional[str] = None
    video_source: Optional[str] = None
    video_thumbnail: Optional[str] = None
    overall_score: Optional[float] = None
    created_at: str

    model_config = {"from_attributes": True}


class AnalysisListResponse(BaseModel):
    items: List[AnalysisListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProgressEvent(BaseModel):
    analysis_id: str
    status: str
    stage: str
    stage_label: str
    progress: int
    message: str
    estimated_seconds_remaining: Optional[int] = None
    error: Optional[dict] = None


# ── Result schemas ────────────────────────────────────────────────────────────

class VideoInfo(BaseModel):
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    source: Optional[str] = None


class ScoreSummary(BaseModel):
    overall_score: float
    rating: str
    summary: Optional[str] = None


class Scores(BaseModel):
    hook: float = 0.0
    cta: float = 0.0
    tone: float = 0.0
    visual: float = 0.0
    pacing: float = 0.0
    clarity: float = 0.0
    engagement: float = 0.0


class HookDetected(BaseModel):
    text: str
    start: float
    end: float
    type: str
    score: float
    reason: Optional[str] = None


class HooksResult(BaseModel):
    hook_score: float
    best_hook: Optional[HookDetected] = None
    hooks: List[HookDetected] = []
    opening_analysis: dict = {}
    recommendations: List[str] = []


class CTADetected(BaseModel):
    text: str
    start: float
    end: float
    type: str
    strength: str
    score: float


class CTAsResult(BaseModel):
    cta_score: float
    ctas: List[CTADetected] = []
    has_cta: bool = False
    recommendations: List[str] = []


class ToneAnalysis(BaseModel):
    primary_tone: Optional[str] = None
    sentiment: Optional[str] = None
    emotions: dict = {}
    energy_score: float = 0.0
    clarity_score: float = 0.0
    confidence_score: float = 0.0
    observations: List[str] = []


class KeyMoment(BaseModel):
    timestamp: float
    frame_url: Optional[str] = None
    impact: str
    type: str
    reason: Optional[str] = None


class VisualAnalysis(BaseModel):
    visual_score: float = 0.0
    key_moments: List[KeyMoment] = []
    recommendations: List[str] = []
    status: str = "completed"


class TimelineEvent(BaseModel):
    start: float
    end: float
    type: str
    severity: str
    message: str


class PacingAnalysis(BaseModel):
    pacing_score: float = 0.0
    words_per_minute: Optional[float] = None
    silence_ratio: Optional[float] = None
    scene_change_frequency: Optional[float] = None
    timeline_events: List[TimelineEvent] = []
    audio_signals: dict = {}


class EngagementAnalysis(BaseModel):
    engagement_score: float = 0.0
    contributing_signals: dict = {}
    note: str = "This is an estimated heuristic score, not actual viewer analytics."


class TranscriptInfo(BaseModel):
    language: Optional[str] = None
    full_text: Optional[str] = None
    word_count: int = 0
    words_per_minute: Optional[float] = None
    duration: Optional[float] = None
    segments: List[dict] = []


class RecommendationOut(BaseModel):
    title: str
    description: str
    priority: str
    category: Optional[str] = None
    timestamp: Optional[float] = None
    reason: Optional[str] = None
    suggested_action: Optional[str] = None


class ScriptSection(BaseModel):
    type: str
    text: str
    estimated_duration: int


class GeneratedScriptOut(BaseModel):
    title: Optional[str] = None
    hook: Optional[str] = None
    sections: List[ScriptSection] = []
    full_script: Optional[str] = None
    estimated_duration: Optional[int] = None
    changes: List[str] = []
    platform: Optional[str] = None
    tone: Optional[str] = None
    version: int = 1


class ReportInfo(BaseModel):
    xlsx_available: bool = False
    json_available: bool = False


class AnalysisResult(BaseModel):
    analysis_id: str
    status: str
    video: Optional[VideoInfo] = None
    summary: Optional[ScoreSummary] = None
    scores: Optional[Scores] = None
    hooks: Optional[HooksResult] = None
    cta: Optional[CTAsResult] = None
    tone: Optional[ToneAnalysis] = None
    visual: Optional[VisualAnalysis] = None
    pacing: Optional[PacingAnalysis] = None
    engagement: Optional[EngagementAnalysis] = None
    transcript: Optional[TranscriptInfo] = None
    timeline: List[TimelineEvent] = []
    recommendations: List[RecommendationOut] = []
    generated_script: Optional[GeneratedScriptOut] = None
    report: Optional[ReportInfo] = None
    error: Optional[dict] = None


class ScriptRegenerateRequest(BaseModel):
    tone: Optional[str] = None
    platform: Optional[str] = None
    audience: Optional[str] = None
    target_duration: Optional[int] = None
    goal: Optional[str] = None
    style: Optional[str] = None
