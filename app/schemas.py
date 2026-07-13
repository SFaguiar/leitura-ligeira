from pydantic import BaseModel


class DocumentCreate(BaseModel):
    title: str
    raw_text: str
    visibility: str = "house"


class DocumentRename(BaseModel):
    title: str


class DocumentSummary(BaseModel):
    id: int
    title: str
    format: str
    source_type: str
    word_count: int
    visibility: str
    owner_id: int | None
    created_at: str
    progress_position: int | None = None
    progress_status: str | None = None


class DocumentDetail(DocumentSummary):
    raw_text: str


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


class UserSettingsUpdate(BaseModel):
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
