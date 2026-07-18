from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentCreate(StrictRequest):
    title: str = Field(max_length=200)
    raw_text: str = Field(max_length=500_000)
    visibility: Literal["house", "private"] = "house"


class DocumentUpdate(StrictRequest):
    title: str | None = Field(default=None, max_length=200)
    collection: str | None = Field(default=None, max_length=100)


class DocumentSummary(BaseModel):
    id: int
    title: str
    format: str
    source_type: str
    word_count: int
    visibility: str
    owner_id: int | None
    collection: str
    created_at: str
    progress_position: int | None = None
    progress_status: str | None = None


class TocEntry(BaseModel):
    title: str
    token_index: int


class DocumentDetail(DocumentSummary):
    raw_text: str
    toc: list[TocEntry] | None = None


class UrlImportRequest(StrictRequest):
    url: str = Field(min_length=1, max_length=2048)
    title: str = Field(default="", max_length=200)
    visibility: Literal["house", "private"] = "house"


class UserCreate(StrictRequest):
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class UserPublic(BaseModel):
    id: int
    name: str


class UserMe(BaseModel):
    id: int
    name: str
    role: str


class UserSettingsOut(BaseModel):
    active_mode: str
    wpm_focus: int
    wpm_flow: int
    chunk_focus: int
    chunk_flow: int
    font_focus: int
    font_flow: int
    orp_enabled: bool
    nav_snap_back_on_click: bool
    nav_pause_on_switch: bool
    theme: str
    collect_stats: bool
    skin: Literal["library", "odysseus"]


class UserSettingsUpdate(StrictRequest):
    skin: Literal["library", "odysseus"] | None = None
    active_mode: Literal["focus", "flow"] | None = None
    wpm_focus: int | None = Field(default=None, ge=100, le=1000)
    wpm_flow: int | None = Field(default=None, ge=100, le=1000)
    chunk_focus: int | None = Field(default=None, ge=1, le=4)
    chunk_flow: int | None = Field(default=None, ge=1, le=4)
    font_focus: int | None = Field(default=None, ge=24, le=96)
    font_flow: int | None = Field(default=None, ge=24, le=96)
    orp_enabled: bool | None = None
    nav_snap_back_on_click: bool | None = None
    nav_pause_on_switch: bool | None = None
    theme: Literal["light", "dark"] | None = None
    collect_stats: bool | None = None


class ProgressOut(BaseModel):
    document_id: int
    position: int
    status: str
    updated_at: str


class ProgressUpdate(StrictRequest):
    position: int | None = Field(default=None, ge=0)
    status: Literal["quero_ler", "lendo", "lido", "abandonado"] | None = None


class SessionCreate(StrictRequest):
    document_id: int = Field(gt=0)
    mode: Literal["focus", "flow"]
    start_pointer: int = Field(default=0, ge=0)


class SessionOut(BaseModel):
    session_id: int | None


class SessionUpdate(StrictRequest):
    end_pointer: int = Field(ge=0)
    position: int = Field(ge=0)
    ended_at: bool = False
    avg_wpm: float | None = Field(default=None, ge=0, le=5000)


class StatsSummary(BaseModel):
    words: int
    reading_seconds: int
    sessions: int
    avg_wpm: float | None
    streak_days: int
    completion_rate: float
    completed_documents: int
    engaged_documents: int


class StatsDailyPoint(BaseModel):
    date: str
    words: int
    reading_seconds: int
    sessions: int


class StatsModeBreakdown(BaseModel):
    mode: str
    words: int
    reading_seconds: int
    sessions: int
    avg_wpm: float | None


class StatsDocumentBreakdown(BaseModel):
    document_id: int
    title: str
    words: int
    reading_seconds: int
    sessions: int
    avg_wpm: float | None


class StatsDashboard(BaseModel):
    scope: str
    period_days: int | None
    generated_at: str
    collecting: bool
    participants: int
    summary: StatsSummary
    daily: list[StatsDailyPoint]
    modes: list[StatsModeBreakdown]
    documents: list[StatsDocumentBreakdown]


class TtsBlockRequest(StrictRequest):
    token: int = Field(default=0, ge=0)
    voice: str | None = Field(default=None, max_length=80)


class TtsWordTimestamp(BaseModel):
    idx: int  # global token index (matches the frontend engine.pointer space)
    start: float
    end: float


class TtsBlockDetail(BaseModel):
    id: int
    document_id: int
    start_token: int
    end_token: int
    voice: str
    model_version: str
    alignment_score: float
    audio_url: str
    timestamps: list[TtsWordTimestamp]


class TtsVoices(BaseModel):
    voices: list[str]
    default: str
    available: bool = True
    reason: str | None = None
    retry_after: int | None = None


class HealthOut(BaseModel):
    version: str
    status: Literal["healthy", "unhealthy"]
    database: Literal["healthy", "unavailable"]


class DiagnosticComponent(BaseModel):
    status: Literal["healthy", "degraded", "unavailable", "not_required"]
    required: bool
    message: str
    version: str | None = None
    latency_ms: int | None = None
    details: dict[str, object] | None = None


class SystemDiagnostics(BaseModel):
    version: str
    status: Literal["healthy", "degraded", "unhealthy"]
    generated_at: str
    components: dict[str, DiagnosticComponent]
