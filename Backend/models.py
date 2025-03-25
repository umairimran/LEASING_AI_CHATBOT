from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class SearchRequest(BaseModel):
    user_id: str
    document_name: str
    query: str
    limit: Optional[int] = 5
    alpha: Optional[float] = 0.5

class SearchResult(BaseModel):
    text: str
    full_text: str
    score: float
    document_name: Optional[str] = None  # Optional field for document source


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int

class ChatRequest(BaseModel):
    user_id: str
    document_name: str
    query: str
    limit: Optional[int] = 5
    alpha: Optional[float] = 0.5

class ChatResponse(BaseModel):
    answer: str 

