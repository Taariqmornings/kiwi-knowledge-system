from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class CategorySchema(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None

    class Config:
        from_attributes = True

class ArchiveSchema(BaseModel):
    id: str
    name: str
    path: str
    title: Optional[str] = None
    description: Optional[str] = None
    creator: Optional[str] = None
    date: Optional[str] = None
    language: Optional[str] = None
    size_bytes: int
    article_count: int
    status: str
    indexed_count: int
    is_extracted: bool = False
    created_at: datetime
    categories: List[CategorySchema] = []

    class Config:
        from_attributes = True

class ArticleResultSchema(BaseModel):
    id: int
    archive_id: str
    archive_title: Optional[str] = None
    title: str
    path: str
    summary: Optional[str] = None
    keywords: Optional[str] = None
    mimetype: str
    score: Optional[float] = None
    title_highlight: Optional[str] = None
    snippet: Optional[str] = None

    class Config:
        from_attributes = True

class AutocompleteItem(BaseModel):
    title: str
    path: str
    archive_id: str
    archive_title: str

class AutocompleteResponse(BaseModel):
    suggestions: List[AutocompleteItem]

class SearchResponse(BaseModel):
    results: List[ArticleResultSchema]
    total_count: int
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
    has_next: bool = False
    has_previous: bool = False

class IndexStatus(BaseModel):
    status: str
    progress: int
    total: int

class IndexJobResponse(BaseModel):
    id: int
    archive_id: str
    status: str
    progress: int
    total: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ScanDirectoryRequest(BaseModel):
    directory: str

class AddFilesRequest(BaseModel):
    files: List[str]

class AppSettings(BaseModel):
    zim_scan_path: str = ""
