from fastapi import APIRouter, HTTPException, Request, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from fastbot.decorators import inject
from fastbot.logger.logger import Logger
from .dependencies import get_current_user_from_request
from services import AuthService, UserGroupService, ContainerService, ApiService
from models import User, UserCreate, UserGroup, Container, Tariff, Label
from models.roles.user_role import UserRole
from models.roles.group_role import GroupRole
from models.permissions.container_permission import ContainerPermission
from datetime import datetime
import traceback

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
            "tg_id": user.tg_id,
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
                "tg_id": str(user.tg_id) if user.tg_id else None,
                "is_active": user.is_active,
            }
        )

    return {"data": users_data}


@router.patch("/users/{user_id}/role")
@inject("auth_service")
async def update_user_role(
    user_id: str,
    request: Request,
    auth_service: AuthService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    new_role = body.get("role")

    if not new_role:
        raise HTTPException(status_code=400, detail="Role is required")

    if new_role not in [r.value for r in UserRole]:
        raise HTTPException(status_code=400, detail=f"Invalid role: {new_role}")

    if (
        new_role in [UserRole.super_admin, UserRole.admin]
        and current_user.role != UserRole.super_admin
    ):
        raise HTTPException(
            status_code=403, detail="Only super admin can assign admin roles"
        )

    user_result = await auth_service.get_user_by_id(user_id)
    if user_result.is_err():
        raise HTTPException(status_code=404, detail="User not found")

    user = user_result.unwrap()

    if str(user.id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    update_result = await auth_service.update_user_role(user_id, new_role)
    if update_result.is_err():
        raise HTTPException(
            status_code=500, detail=f"Error updating role: {update_result.unwrap_err()}"
        )

    updated_user = update_result.unwrap()
    return {
        "data": {
            "id": str(updated_user.id),
            "name": updated_user.username or updated_user.first_name,
            "email": updated_user.email or "",
            "role": updated_user.role,
            "tg_id": str(updated_user.tg_id) if updated_user.tg_id else None,
            "is_active": updated_user.is_active,
        }
    }


@router.patch("/users/{user_id}/status")
@inject("auth_service")
async def update_user_status(
    user_id: str,
    request: Request,
    auth_service: AuthService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    is_active = body.get("is_active")

    if is_active is None:
        raise HTTPException(status_code=400, detail="is_active field is required")

    user_result = await auth_service.get_user_by_id(user_id)
    if user_result.is_err():
        raise HTTPException(status_code=404, detail="User not found")

    user = user_result.unwrap()

    if str(user.id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot change your own status")

    update_result = await auth_service.update_user_status(user_id, is_active)
    if update_result.is_err():
        raise HTTPException(
            status_code=500,
            detail=f"Error updating status: {update_result.unwrap_err()}",
        )

    updated_user = update_result.unwrap()
    return {
        "data": {
            "id": str(updated_user.id),
            "name": updated_user.username or updated_user.first_name,
            "email": updated_user.email or "",
            "role": updated_user.role,
            "tg_id": str(updated_user.tg_id) if updated_user.tg_id else None,
            "is_active": updated_user.is_active,
        }
    }


def _extract_member_info(m: dict, auth_service_get_user=None) -> dict:
    user_id = str(m.get("user_id", ""))
    role = m.get("role", "member")
    if hasattr(role, "value"):
        role = role.value

    user_name = user_id
    user_email = ""

    if auth_service_get_user:
        try:
            user_result = auth_service_get_user(user_id)
            if hasattr(user_result, "is_ok") and user_result.is_ok():
                user = user_result.unwrap()
                user_name = user.username or user.first_name or user_id
                user_email = user.email or ""
        except Exception:
            pass

    return {
        "user_id": user_id,
        "user_name": m.get("user_name", user_name),
        "user_email": user_email,
        "role": role,
        "joined_at": m.get("joined_at"),
    }


def _extract_container_access_info(c: dict) -> dict:
    container_id = c.get("container_id", "")
    if not container_id:
        container_id = c.get("id", "")

    permission = c.get("permission", "read_write")
    if hasattr(permission, "value"):
        permission = permission.value

    return {
        "container_id": str(container_id),
        "permission": str(permission),
    }


@router.get("/groups")
@inject("auth_service")
@inject("user_group_service")
async def list_user_groups(
    auth_service: AuthService,
    user_group_service: UserGroupService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    groups_result = await user_group_service.get_all_groups()
    if groups_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching groups")

    groups = groups_result.unwrap()
    groups_data = []

    for group in groups:
        members_result = await user_group_service.get_group_members(group.id)
        raw_members = members_result.unwrap() if members_result.is_ok() else []

        containers_result = await user_group_service.get_group_containers(group)
        raw_containers = containers_result.unwrap() if containers_result.is_ok() else []

        members_data = []
        for m in raw_members:
            user_id = str(m.get("user_id", ""))
            role = m.get("role", "member")
            if hasattr(role, "value"):
                role = role.value

            user_name = user_id
            try:
                user_result = await auth_service.get_user_by_id(user_id)
                if user_result.is_ok():
                    u = user_result.unwrap()
                    user_name = u.username or u.first_name or user_id
            except Exception:
                pass

            members_data.append(
                {
                    "user_id": user_id,
                    "user_name": m.get("user_name", user_name),
                    "role": role,
                }
            )

        containers_data = []
        for c in raw_containers:
            container_id = c.get("container_id", c.get("id", ""))
            permission = c.get("permission", "read_write")
            if hasattr(permission, "value"):
                permission = permission.value

            containers_data.append(
                {
                    "container_id": str(container_id),
                    "permission": str(permission),
                }
            )

        groups_data.append(
            {
                "id": group.id,
                "name": group.id,
                "description": group.description,
                "color": getattr(group, "color", "#ff9800"),
                "created_at": str(group.created_at) if group.created_at else None,
                "members": members_data,
                "containers": containers_data,
            }
        )

    return {"data": groups_data}


@router.post("/groups")
@inject("auth_service")
@inject("user_group_service")
async def create_user_group(
    request: Request,
    auth_service: AuthService,
    user_group_service: UserGroupService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    name = body.get("name")
    description = body.get("description", "")
    color = body.get("color", "#ff9800")

    if not name:
        raise HTTPException(status_code=400, detail="Group name is required")

    group = UserGroup(
        id=name,
        description=description,
        created_at=datetime.now(),
        color=color,
    )

    create_result = await user_group_service.create_user_group(group)
    if create_result.is_err():
        error = create_result.unwrap_err()
        if "already exists" in str(error).lower():
            raise HTTPException(
                status_code=409, detail=f"Group '{name}' already exists"
            )
        raise HTTPException(status_code=500, detail=f"Error creating group: {error}")

    created_group = create_result.unwrap()
    return {
        "data": {
            "id": created_group.id,
            "name": created_group.id,
            "description": created_group.description,
            "color": getattr(created_group, "color", color),
            "created_at": (
                str(created_group.created_at) if created_group.created_at else None
            ),
            "members": [],
            "containers": [],
        }
    }


@router.patch("/groups/{group_id}")
@inject("auth_service")
@inject("user_group_service")
async def update_user_group(
    group_id: str,
    request: Request,
    auth_service: AuthService,
    user_group_service: UserGroupService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()

    update_result = await user_group_service.update_user_group(
        group_id,
        name=body.get("name"),
        description=body.get("description"),
        color=body.get("color"),
    )

    if update_result.is_err():
        raise HTTPException(
            status_code=500,
            detail=f"Error updating group: {update_result.unwrap_err()}",
        )

    updated_group = update_result.unwrap()

    members_result = await user_group_service.get_group_members(group_id)
    raw_members = members_result.unwrap() if members_result.is_ok() else []

    containers_result = await user_group_service.get_group_containers(updated_group)
    raw_containers = containers_result.unwrap() if containers_result.is_ok() else []

    members_data = []
    for m in raw_members:
        user_id = str(m.get("user_id", ""))
        role = m.get("role", "member")
        if hasattr(role, "value"):
            role = role.value

        user_name = user_id
        try:
            user_result = await auth_service.get_user_by_id(user_id)
            if user_result.is_ok():
                u = user_result.unwrap()
                user_name = u.username or u.first_name or user_id
        except Exception:
            pass

        members_data.append(
            {
                "user_id": user_id,
                "user_name": m.get("user_name", user_name),
                "role": role,
            }
        )

    containers_data = []
    for c in raw_containers:
        container_id = c.get("container_id", c.get("id", ""))
        permission = c.get("permission", "read_write")
        if hasattr(permission, "value"):
            permission = permission.value

        containers_data.append(
            {
                "container_id": str(container_id),
                "permission": str(permission),
            }
        )

    return {
        "data": {
            "id": updated_group.id,
            "name": updated_group.id,
            "description": updated_group.description,
            "color": getattr(updated_group, "color", "#ff9800"),
            "created_at": (
                str(updated_group.created_at) if updated_group.created_at else None
            ),
            "members": members_data,
            "containers": containers_data,
        }
    }


@router.delete("/groups/{group_id}")
@inject("auth_service")
@inject("user_group_service")
async def delete_user_group(
    group_id: str,
    request: Request,
    auth_service: AuthService,
    user_group_service: UserGroupService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    delete_result = await user_group_service.delete_user_group(group_id)
    if delete_result.is_err():
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting group: {delete_result.unwrap_err()}",
        )

    await user_group_service.delete_all_members(group_id)
    await user_group_service.delete_all_container_accesses(group_id)

    return {"message": "Group deleted successfully"}


@router.get("/groups/{group_id}/members")
@inject("auth_service")
@inject("user_group_service")
async def get_group_members(
    group_id: str,
    request: Request,
    auth_service: AuthService,
    user_group_service: UserGroupService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    members_result = await user_group_service.get_group_members(group_id)
    if members_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching members")

    raw_members = members_result.unwrap()
    members_data = []

    for member in raw_members:
        user_id = str(member.get("user_id", ""))
        role = member.get("role", "member")
        if hasattr(role, "value"):
            role = role.value

        user_name = user_id
        user_email = ""

        try:
            user_result = await auth_service.get_user_by_id(user_id)
            if user_result.is_ok():
                user = user_result.unwrap()
                user_name = user.username or user.first_name or user_id
                user_email = user.email or ""
        except Exception:
            pass

        members_data.append(
            {
                "user_id": user_id,
                "user_name": user_name,
                "user_email": user_email,
                "role": role,
                "joined_at": member.get("joined_at"),
            }
        )

    return {"data": members_data}


@router.post("/groups/{group_id}/members")
@inject("auth_service")
@inject("user_group_service")
async def add_member_to_group(
    group_id: str,
    request: Request,
    auth_service: AuthService,
    user_group_service: UserGroupService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    user_id = body.get("user_id")
    role = body.get("role", "member")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    user_result = await auth_service.get_user_by_id(user_id)
    if user_result.is_err():
        raise HTTPException(status_code=404, detail="User not found")

    user = user_result.unwrap()

    group_result = await user_group_service.get_group_by_id(group_id)
    if group_result.is_err():
        raise HTTPException(status_code=404, detail="Group not found")

    group = group_result.unwrap()

    try:
        group_role = GroupRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")

    add_result = await user_group_service.add_user_to_group(user, group, group_role)
    if add_result.is_err():
        error = add_result.unwrap_err()
        if "already" in str(error).lower():
            raise HTTPException(
                status_code=409, detail="User is already a member of this group"
            )
        raise HTTPException(status_code=500, detail=f"Error adding user: {error}")

    return {"message": "User added to group successfully"}


@router.delete("/groups/{group_id}/members/{user_id}")
@inject("auth_service")
@inject("user_group_service")
async def remove_member_from_group(
    group_id: str,
    user_id: str,
    request: Request,
    auth_service: AuthService,
    user_group_service: UserGroupService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    user_result = await auth_service.get_user_by_id(user_id)
    if user_result.is_err():
        raise HTTPException(status_code=404, detail="User not found")

    user = user_result.unwrap()

    group_result = await user_group_service.get_group_by_id(group_id)
    if group_result.is_err():
        raise HTTPException(status_code=404, detail="Group not found")

    group = group_result.unwrap()

    remove_result = await user_group_service.delete_user_from_group(user, group)
    if remove_result.is_err():
        raise HTTPException(
            status_code=500, detail=f"Error removing user: {remove_result.unwrap_err()}"
        )

    return {"message": "User removed from group successfully"}


@router.patch("/groups/{group_id}/members/{user_id}")
@inject("auth_service")
@inject("user_group_service")
async def update_member_role(
    group_id: str,
    user_id: str,
    request: Request,
    auth_service: AuthService,
    user_group_service: UserGroupService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    new_role = body.get("role")

    if not new_role:
        raise HTTPException(status_code=400, detail="role is required")

    try:
        group_role = GroupRole(new_role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {new_role}")

    update_result = await user_group_service.update_member_role(
        group_id, user_id, group_role
    )
    if update_result.is_err():
        raise HTTPException(
            status_code=500, detail=f"Error updating role: {update_result.unwrap_err()}"
        )

    return {"message": "Member role updated successfully"}


@router.get("/containers/{container_id}/access")
@inject("auth_service")
@inject("user_group_service")
async def get_container_accesses(
    container_id: str,
    request: Request,
    auth_service: AuthService,
    user_group_service: UserGroupService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    accesses_result = await user_group_service.get_container_accesses(container_id)
    if accesses_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching accesses")

    raw_accesses = accesses_result.unwrap()

    accesses_data = []
    for a in raw_accesses:
        permission = a.get("permission", "read_write")
        if hasattr(permission, "value"):
            permission = permission.value

        accesses_data.append(
            {
                "container_id": str(a.get("container_id", container_id)),
                "group_id": str(a.get("group_id", "")),
                "permission": str(permission),
            }
        )

    return {"data": accesses_data}


@router.post("/containers/{container_id}/access")
@inject("auth_service")
@inject("user_group_service")
@inject("container_service")
async def grant_container_access(
    container_id: str,
    request: Request,
    auth_service: AuthService,
    user_group_service: UserGroupService,
    container_service: ContainerService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    group_id = body.get("group_id")
    permission = body.get("permission", "read_write")

    if not group_id:
        raise HTTPException(status_code=400, detail="group_id is required")

    container_result = await container_service.get_container(container_id)
    if container_result.is_err():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()

    group_result = await user_group_service.get_group_by_id(group_id)
    if group_result.is_err():
        raise HTTPException(status_code=404, detail="Group not found")

    group = group_result.unwrap()

    try:
        container_permission = ContainerPermission(permission)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid permission: {permission}")

    grant_result = await user_group_service.add_container_to_group(
        container, group, container_permission
    )
    if grant_result.is_err():
        error = grant_result.unwrap_err()
        if "already" in str(error).lower():
            raise HTTPException(
                status_code=409, detail="Group already has access to this container"
            )
        raise HTTPException(status_code=500, detail=f"Error granting access: {error}")

    return {"message": "Access granted successfully"}


@router.delete("/containers/{container_id}/access/{group_id}")
@inject("auth_service")
@inject("user_group_service")
@inject("container_service")
async def revoke_container_access(
    container_id: str,
    group_id: str,
    request: Request,
    auth_service: AuthService,
    user_group_service: UserGroupService,
    container_service: ContainerService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    container_result = await container_service.get_container(container_id)
    if container_result.is_err():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()

    group_result = await user_group_service.get_group_by_id(group_id)
    if group_result.is_err():
        raise HTTPException(status_code=404, detail="Group not found")

    group = group_result.unwrap()

    revoke_result = await user_group_service.delete_container_from_group(
        container, group
    )
    if revoke_result.is_err():
        raise HTTPException(
            status_code=500,
            detail=f"Error revoking access: {revoke_result.unwrap_err()}",
        )

    return {"message": "Access revoked successfully"}


@router.post("/containers")
@inject("auth_service")
@inject("container_service")
@inject("api_service")
async def create_container_as_admin(
    request: Request,
    auth_service: AuthService,
    container_service: ContainerService,
    api_service: ApiService,
):
    current_user = await get_current_user_from_request(request, auth_service)

    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        body = await request.json()

        user_id = body.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        target_user_result = await auth_service.get_user_by_id(user_id)
        if target_user_result.is_err():
            user_by_tg_result = await auth_service.get_user_by_tg_id(user_id)
            if user_by_tg_result.is_err():
                raise HTTPException(status_code=404, detail="Target user not found")
            target_user = user_by_tg_result.unwrap()
            target_user_id_for_backend = str(target_user.tg_id)
        else:
            target_user = target_user_result.unwrap()
            target_user_id_for_backend = (
                str(target_user.tg_id) if target_user.tg_id else str(target_user.id)
            )

        container_id = body.get("container_id")
        if not container_id:
            raise HTTPException(status_code=400, detail="container_id is required")

        tariff = Tariff(
            memory_limit=body.get("memory_limit", 512 * 1024 * 1024),
            storage_quota=body.get("storage_quota", 1024 * 1024 * 1024),
            file_limit=body.get("file_limit", 1000),
        )

        env_label_data = body.get("env_label", {"key": "default", "value": "Default"})
        env_label = Label(
            key=env_label_data.get("key", "default"),
            value=env_label_data.get("value", "Default"),
        )

        type_label_data = body.get(
            "type_label", {"key": "standard", "value": "Standard"}
        )
        type_label = Label(
            key=type_label_data.get("key", "standard"),
            value=type_label_data.get("value", "Standard"),
        )

        container = Container(
            id=container_id,
            user_id=target_user_id_for_backend,
            tariff=tariff,
            env_label=env_label,
            type_label=type_label,
            privileged=body.get("privileged", False),
            commands=body.get("commands", []),
        )

        container_data_for_db = {
            "container_id": container.id,
            "user_id": container.user_id,
            "memory_limit": container.tariff.memory_limit,
            "storage_quota": container.tariff.storage_quota,
            "file_limit": container.tariff.file_limit,
            "env_label": {
                "key": container.env_label.key,
                "value": container.env_label.value,
            },
            "type_label": {
                "key": container.type_label.key,
                "value": container.type_label.value,
            },
            "commands": container.commands,
            "privileged": container.privileged,
        }

        container_result = await container_service.create_container(
            container_data_for_db
        )

        if container_result.is_err():
            error = container_result.unwrap_err()
            Logger.error(f"Container creation failed: {error}")
            if "already exists" in str(error).lower():
                raise HTTPException(
                    status_code=409,
                    detail=f"Container with ID '{container.id}' already exists",
                )
            raise HTTPException(
                status_code=500, detail=f"Error creating container: {str(error)}"
            )

        created_container = container_result.unwrap()

        api_result = await api_service.containers.create_container(
            user_id=target_user_id_for_backend,
            container_id=container.id,
            tariff=tariff,
            env_label=env_label,
            type_label=type_label,
            commands=container.commands,
            privileged=container.privileged,
        )

        if api_result.is_err():
            error = api_result.unwrap_err()
            await container_service.delete_container(
                target_user_id_for_backend, container.id
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create container in backend: {str(error)}",
            )

        response_data = {
            "data": {
                "id": created_container.id,
                "user_id": created_container.user_id,
                "status": "created",
                "memory_limit": created_container.tariff.memory_limit,
                "storage_quota": created_container.tariff.storage_quota,
                "file_limit": created_container.tariff.file_limit,
                "env_label": {
                    "key": created_container.env_label.key,
                    "value": created_container.env_label.value,
                },
                "type_label": {
                    "key": created_container.type_label.key,
                    "value": created_container.type_label.value,
                },
                "commands": created_container.commands,
                "privileged": created_container.privileged,
                "created_at": datetime.now().isoformat(),
                "cpu_usage": 0,
                "memory_usage": 0,
                "storage_used": 0,
            }
        }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in create_container_as_admin: {e}")
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
