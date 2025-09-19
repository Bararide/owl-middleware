from pydantic import BaseModel
from typing import List


class FileCreateResponse(BaseModel):
    path: str
    size: int
    created: bool


class FileReadResponse(BaseModel):
    path: str
    content: str
    size: int


class SearchResult(BaseModel):
    path: str
    score: float


class SemanticSearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    count: int
