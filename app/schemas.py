from typing import Literal

from pydantic import BaseModel

class DocumentCreate(BaseModel):
    title: str
    raw_text: str
    visibility: str = "house"


class DocumentUpdate(BaseModel):
    title: str | None = None
    collection: str | None = None


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


class UrlImportRequest(BaseModel):
    url: str
    title: str = ""
    visibility: str = "house"


class UserCreate(BaseModel):
    name: str
    password: str


class LoginRequest(BaseModel):
    name: str
    password: str


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


class UserSettingsUpdate(BaseModel):
    skin: Literal["library", "odysseus"] | None = None
    active_mode: str | None = None
    wpm_focus: int | None = None
    wpm_flow: int | None = None
    chunk_focus: int | None = None
    chunk_flow: int | None = None
    font_focus: int | None = None
    font_flow: int | None = None
    orp_enabled: bool | None = None
    nav_snap_back_on_click: bool | None = None
    nav_pause_on_switch: bool | None = None
    theme: str | None = None
    collect_stats: bool | None = None


class ProgressOut(BaseModel):
    document_id: int
    position: int
    status: str
    updated_at: str


class ProgressUpdate(BaseModel):
    position: int | None = None
    status: str | None = None


class SessionCreate(BaseModel):
    document_id: int
    mode: str
    start_pointer: int = 0


class SessionOut(BaseModel):
    session_id: int | None


class SessionUpdate(BaseModel):
    end_pointer: int
    position: int
    ended_at: bool = False
    avg_wpm: float | None = None


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


class TtsBlockRequest(BaseModel):
    token: int = 0
    voice: str | None = None


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
