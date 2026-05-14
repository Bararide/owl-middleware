from . import (
    auth,
    chat,
    containers,
    files,
    health,
    ocr,
    recommendations,
    search,
    groups,
)
from fastapi import APIRouter

http_router = APIRouter()

http_router.include_router(auth.router)
http_router.include_router(chat.router)
http_router.include_router(containers.router)
http_router.include_router(files.router)
http_router.include_router(health.router)
http_router.include_router(ocr.router)
http_router.include_router(recommendations.router)
http_router.include_router(search.router)
http_router.include_router(groups.router)

__all__ = [
    "auth",
    "chat",
    "containers",
    "files",
    "health",
    "ocr",
    "recommendations",
    "search",
    "groups",
    "http_router",
]
