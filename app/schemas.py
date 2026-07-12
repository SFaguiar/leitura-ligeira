from pydantic import BaseModel


class DocumentCreate(BaseModel):
    title: str
    raw_text: str


class DocumentRename(BaseModel):
    title: str


class DocumentSummary(BaseModel):
    id: int
    title: str
    format: str
    source_type: str
    created_at: str


class DocumentDetail(DocumentSummary):
    raw_text: str
