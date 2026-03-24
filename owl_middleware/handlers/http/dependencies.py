from fastapi import HTTPException, Request
from services import AuthService
from models import User


async def get_current_user_from_request(
    request: Request,
    auth_service: AuthService,
) -> User:
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    user_result = await auth_service.get_user_by_token(token)
    if user_result.is_err():
        raise HTTPException(status_code=401, detail="Invalid token")

    return user_result.unwrap()
