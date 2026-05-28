from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from fastbot.decorators import inject
from .dependencies import get_current_user_from_request
from services import AuthService
from models import User, UserCreate
from models.roles.user_role import UserRole

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer()


@router.post("/login")
@inject("auth_service")
async def admin_login(
    request: Request,
    auth_service: AuthService,
):
    body = await request.json()
    email = body.get("email")
    password = body.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    result = await auth_service.admin_login(email, password)
    if result.is_err():
        error = result.unwrap_err()
        if "Admin rights" in str(error):
            raise HTTPException(status_code=403, detail=str(error))
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = result.unwrap()

    user_result = await auth_service.get_user_by_email(email)
    if user_result.is_ok():
        user = user_result.unwrap()
        user_data = {
            "id": user.id,
            "username": user.username or user.first_name,
            "email": user.email,
            "role": user.role,
            "permissions": getattr(
                user, "permissions", auth_service._get_default_permissions(user.role)
            ),
        }
    else:
        user_data = None

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_data,
        "expires_in": 8 * 3600,
    }


@router.get("/verify")
@inject("auth_service")
async def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = None,
):
    token = credentials.credentials

    result = await auth_service.verify_admin_token(token)
    if result.is_err():
        raise HTTPException(status_code=401, detail=str(result.unwrap_err()))

    payload = result.unwrap()

    return {
        "valid": True,
        "user": {
            "id": payload.get("user_id"),
            "email": payload.get("email"),
            "username": payload.get("username"),
            "role": payload.get("role"),
            "permissions": payload.get("permissions", []),
        },
    }


@router.get("/users")
@inject("auth_service")
async def list_all_users(
    auth_service: AuthService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    users_result = await auth_service.get_all_users()
    if users_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching users")

    users = users_result.unwrap()

    users_data = []
    for user in users:
        users_data.append(
            {
                "id": str(user.id),
                "name": user.username or user.first_name,
                "email": user.email or "",
                "role": user.role,
                "tg_id": user.tg_id,
                "is_active": user.is_active,
            }
        )

    return {"data": users_data}


@router.post("/create-first-admin")
@inject("auth_service")
async def create_first_admin(
    request: Request,
    auth_service: AuthService,
):
    body = await request.json()
    email = body.get("email")
    password = body.get("password")
    username = body.get("username", "Admin")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    existing_admins = await auth_service.users.find_one(
        {"role": {"$in": [UserRole.admin, UserRole.super_admin]}}
    )

    if existing_admins:
        raise HTTPException(status_code=403, detail="Admin already exists")

    user_create = UserCreate(
        email=email,
        password=password,
        first_name=username,
        auth_method="email",
        role=UserRole.super_admin,
        permissions=["*"],
    )

    result = await auth_service.create_user(user_create)
    if result.is_err():
        raise HTTPException(status_code=400, detail=str(result.unwrap_err()))

    user = result.unwrap()
    token = auth_service.generate_admin_token(user)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username or user.first_name,
            "email": user.email,
            "role": user.role,
            "permissions": ["*"],
        },
    }
