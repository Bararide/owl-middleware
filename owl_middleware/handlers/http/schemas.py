from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class RegisterRequest(BaseModel):
    email: str
    password: str
    first_name: str = "Unknown"
    last_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateContainerRequest(BaseModel):
    container_id: str
    memory_limit: int
    storage_quota: int
    file_limit: int
    env_label: Optional[Dict[str, str]] = None
    type_label: Optional[Dict[str, str]] = None
    commands: List[str] = ["search", "debug", "all", "create"]
    privileged: bool = False


class OcrRequest(BaseModel):
    container_id: str
    file_data: str
    file_name: str
    mime_type: str = "image/jpeg"


class ChatRequest(BaseModel):
    query: str
    container_id: str
    conversation_history: List[Dict[str, Any]] = []
    model: int = 0
    limit: int = 5


class SemanticSearchRequest(BaseModel):
    query: str
    container_id: str
    limit: int = 10


class SemanticGraphRequest(BaseModel):
    container_id: str
