from fastapi import APIRouter, HTTPException, Request
from fastbot.decorators import inject
from services import ApiService

router = APIRouter(tags=["health"])


@router.get("/health")
@inject("api_service")
async def check_health(
    request: Request,
    api_service: ApiService,
):
    health_check_result = await api_service.system.health_check()
    if health_check_result.is_err():
        raise HTTPException(status_code=500, detail="Health check failed")
    return {"status": "healthy", "success": True}
