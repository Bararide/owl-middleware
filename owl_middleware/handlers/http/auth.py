from fastapi import APIRouter, HTTPException, Request
from fastbot.decorators import inject
from .schemas import RegisterRequest, LoginRequest
from .dependencies import get_current_user_from_request
from services import AuthService
from models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
@inject("auth_service")
async def register_email_user(
    request: RegisterRequest,
    auth_service: AuthService,
):
    user_result = await auth_service.register_email_user(
        request.email,
        request.password,
        {"first_name": request.first_name, "last_name": request.last_name},
    )
    if user_result.is_err():
        raise HTTPException(status_code=400, detail=str(user_result.unwrap_err()))
    user = user_result.unwrap()
    token = auth_service.generate_jwt_token(user)
    return {
        "data": {
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            "token": token,
        }
    }


@router.post("/login")
@inject("auth_service")
async def login_email_user(
    request: LoginRequest,
    auth_service: AuthService,
):
    auth_result = await auth_service.authenticate_email(request.email, request.password)
    if auth_result.is_err():
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = auth_result.unwrap()
    token = auth_service.generate_jwt_token(user)
    return {
        "data": {
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            "token": token,
        }
    }


@router.post("/telegram-token")
@inject("auth_service")
async def get_telegram_token(
    request: Request,
    auth_service: AuthService,
    current_user: User,
):
    if not current_user.tg_id:
        raise HTTPException(status_code=400, detail="Not a Telegram user")
    token = auth_service.generate_jwt_token(current_user)
    return {
        "data": {
            "token": token,
            "user": {
                "id": current_user.id,
                "tg_id": current_user.tg_id,
                "username": current_user.username,
                "first_name": current_user.first_name,
            },
        }
    }


@router.get("/user")
@inject("auth_service")
async def get_user(
    request: Request,
    auth_service: AuthService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    return {
        "data": {
            "id": current_user.id,
            "name": current_user.username,
            "email": current_user.email,
            "role": current_user.is_admin,
        }
    }
