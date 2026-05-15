from fastapi import APIRouter, HTTPException, Request
from fastbot.decorators import inject
from fastbot.logger.logger import Logger
from .dependencies import get_current_user_from_request
from services import GroupService, AuthService, ContainerService, FileService

import traceback

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("/container/{container_id}")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
async def get_container_groups(
    container_id: str,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    container_result = await container_service.get_container(container_id)
    if container_result.is_err():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()
    if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    groups_result = await group_service.get_groups_by_container(container_id)
    if groups_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching groups")

    groups = groups_result.unwrap()
    return {"data": [group.dict() for group in groups]}


@router.post("/container/{container_id}")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
async def create_group(
    container_id: str,
    request: Request,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
):
    try:
        body = await request.json()
        current_user = await get_current_user_from_request(request, auth_service)

        container_result = await container_service.get_container(container_id)
        if container_result.is_err():
            raise HTTPException(status_code=404, detail="Container not found")

        container = container_result.unwrap()
        if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Access denied")

        name = body.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="Group name is required")

        description = body.get("description", "")

        group_result = await group_service.create_group(name, container_id, description)
        if group_result.is_err():
            error = group_result.unwrap_err()
            if "already exists" in str(error).lower():
                raise HTTPException(status_code=409, detail=str(error))
            raise HTTPException(
                status_code=500, detail=f"Error creating group: {str(error)}"
            )

        group = group_result.unwrap()
        return {"data": group.dict(), "message": f"Group {name} created successfully"}

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in create_group: {e}")
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{group_id}")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
async def get_group(
    group_id: str,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    group_result = await group_service.get_group(group_id)
    if group_result.is_err():
        raise HTTPException(status_code=404, detail="Group not found")

    group = group_result.unwrap()

    container_result = await container_service.get_container(group.container_id)
    if container_result.is_err():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()
    if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    return {"data": group.dict()}


@router.patch("/{group_id}")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
async def update_group(
    group_id: str,
    request: Request,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
):
    try:
        body = await request.json()
        current_user = await get_current_user_from_request(request, auth_service)

        group_result = await group_service.get_group(group_id)
        if group_result.is_err():
            raise HTTPException(status_code=404, detail="Group not found")

        group = group_result.unwrap()

        container_result = await container_service.get_container(group.container_id)
        if container_result.is_err():
            raise HTTPException(status_code=404, detail="Container not found")

        container = container_result.unwrap()
        if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Access denied")

        description = body.get("description")
        if description is None:
            raise HTTPException(status_code=400, detail="Description is required")

        update_result = await group_service.update_group(
            group_id, group.container_id, description
        )

        if update_result.is_err():
            error = update_result.unwrap_err()
            raise HTTPException(
                status_code=500, detail=f"Error updating group: {str(error)}"
            )

        if not update_result.unwrap():
            raise HTTPException(status_code=404, detail="Group not found")

        return {"message": f"Group {group_id} updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in update_group: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{group_id}")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
async def delete_group(
    group_id: str,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    group_result = await group_service.get_group(group_id)
    if group_result.is_err():
        raise HTTPException(status_code=404, detail="Group not found")

    group = group_result.unwrap()

    container_result = await container_service.get_container(group.container_id)
    if container_result.is_err():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()
    if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    delete_result = await group_service.delete_group(group_id, group.container_id)
    if delete_result.is_err():
        raise HTTPException(status_code=500, detail="Error deleting group")

    return {"message": f"Group {group_id} deleted successfully"}


@router.post("/{group_id}/files")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
async def add_file_to_group(
    group_id: str,
    request: Request,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
):
    try:
        body = await request.json()
        current_user = await get_current_user_from_request(request, auth_service)

        file_id = body.get("file_id")
        if not file_id:
            raise HTTPException(status_code=400, detail="file_id is required")

        group_result = await group_service.get_group(group_id)
        if group_result.is_err():
            raise HTTPException(status_code=404, detail="Group not found")

        group = group_result.unwrap()

        container_result = await container_service.get_container(group.container_id)
        if container_result.is_err():
            raise HTTPException(status_code=404, detail="Container not found")

        container = container_result.unwrap()
        if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Access denied")

        # content_result = await group_service.api_service.files.get_file_content(file_id, group.container_id)
        # if content_result.is_err():
        #     raise HTTPException(status_code=404, detail="File not found")

        add_result = await group_service.add_file_to_group(file_id, group_id)
        if add_result.is_err():
            error = add_result.unwrap_err()
            if "already in group" in str(error).lower():
                raise HTTPException(status_code=409, detail=str(error))
            raise HTTPException(
                status_code=500, detail=f"Error adding file to group: {str(error)}"
            )

        return {
            "data": add_result.unwrap().dict(),
            "message": f"File {file_id} added to group {group_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in add_file_to_group: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in add_file_to_group: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{group_id}/files/{file_id}")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
async def remove_file_from_group(
    group_id: str,
    file_id: str,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    group_result = await group_service.get_group(group_id)
    if group_result.is_err():
        raise HTTPException(status_code=404, detail="Group not found")

    group = group_result.unwrap()

    container_result = await container_service.get_container(group.container_id)
    if container_result.is_err():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()
    if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    remove_result = await group_service.remove_file_from_group(file_id, group_id)
    if remove_result.is_err():
        raise HTTPException(status_code=500, detail="Error removing file from group")

    if not remove_result.unwrap():
        raise HTTPException(status_code=404, detail="File not found in group")

    return {"message": f"File {file_id} removed from group {group_id}"}


@router.get("/{group_id}/files")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
async def get_group_files(
    group_id: str,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    group_result = await group_service.get_group(group_id)
    if group_result.is_err():
        raise HTTPException(status_code=404, detail="Group not found")

    group = group_result.unwrap()

    container_result = await container_service.get_container(group.container_id)
    if container_result.is_err():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()
    if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    files_result = await group_service.get_files_by_group(group_id)
    if files_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching files")

    files = files_result.unwrap()
    return {
        "data": [
            {"id": f.id, "name": f.name, "container_id": f.container_id} for f in files
        ]
    }


@router.get("/file/{file_id}/groups")
@inject("group_service")
@inject("auth_service")
async def get_file_groups(
    file_id: str,
    group_service: GroupService,
    auth_service: AuthService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    groups_result = await group_service.get_groups_by_file(file_id)
    if groups_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching groups")

    groups = groups_result.unwrap()

    if groups:
        container_id = groups[0].container_id
        from services import ContainerService

        container_service = ContainerService(
            db_service=group_service.db_service,
            api_service=group_service.api_service,
            file_service=group_service.file_service,
        )
        container_result = await container_service.get_container(container_id)
        if container_result.is_ok():
            container = container_result.unwrap()
            if (
                container.user_id != str(current_user.tg_id)
                and not current_user.is_admin
            ):
                raise HTTPException(status_code=403, detail="Access denied")

    return {"data": [group.dict() for group in groups]}


@router.post("/{group_id}/files/batch")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
@inject("file_service")
async def add_multiple_files_to_group(
    group_id: str,
    request: Request,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
    file_service: FileService,
):
    try:
        body = await request.json()
        current_user = await get_current_user_from_request(request, auth_service)

        file_ids = body.get("file_ids", [])
        if not file_ids:
            raise HTTPException(status_code=400, detail="file_ids list is required")

        group_result = await group_service.get_group(group_id)
        if group_result.is_err():
            raise HTTPException(status_code=404, detail="Group not found")

        group = group_result.unwrap()

        container_result = await container_service.get_container(group.container_id)
        if container_result.is_err():
            raise HTTPException(status_code=404, detail="Container not found")

        container = container_result.unwrap()
        if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Access denied")

        add_result = await group_service.add_multiple_files_to_group(file_ids, group_id)
        if add_result.is_err():
            raise HTTPException(status_code=500, detail="Error adding files to group")

        added_files = add_result.unwrap()
        return {
            "message": f"Added {len(added_files)} files to group {group_id}",
            "data": [file.dict() for file in added_files],
        }

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in add_multiple_files_to_group: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{group_id}/files/batch")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
async def remove_multiple_files_from_group(
    group_id: str,
    request: Request,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
):
    try:
        body = await request.json()
        current_user = await get_current_user_from_request(request, auth_service)

        file_ids = body.get("file_ids", [])
        if not file_ids:
            raise HTTPException(status_code=400, detail="file_ids list is required")

        group_result = await group_service.get_group(group_id)
        if group_result.is_err():
            raise HTTPException(status_code=404, detail="Group not found")

        group = group_result.unwrap()

        container_result = await container_service.get_container(group.container_id)
        if container_result.is_err():
            raise HTTPException(status_code=404, detail="Container not found")

        container = container_result.unwrap()
        if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Access denied")

        remove_result = await group_service.remove_multiple_files_from_group(
            file_ids, group_id
        )
        if remove_result.is_err():
            raise HTTPException(
                status_code=500, detail="Error removing files from group"
            )

        removed_count = remove_result.unwrap()
        return {"message": f"Removed {removed_count} files from group {group_id}"}

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in remove_multiple_files_from_group: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{group_id}/move/{file_id}")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
async def move_file_between_groups(
    group_id: str,
    file_id: str,
    request: Request,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
):
    try:
        body = await request.json()
        current_user = await get_current_user_from_request(request, auth_service)

        from_group_id = body.get("from_group_id")
        if not from_group_id:
            raise HTTPException(status_code=400, detail="from_group_id is required")

        to_group_id = group_id

        from_group_result = await group_service.get_group(from_group_id)
        if from_group_result.is_err():
            raise HTTPException(status_code=404, detail="Source group not found")

        from_group = from_group_result.unwrap()
        container_result = await container_service.get_container(
            from_group.container_id
        )
        if container_result.is_err():
            raise HTTPException(status_code=404, detail="Container not found")

        container = container_result.unwrap()
        if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Access denied")

        to_group_result = await group_service.get_group(to_group_id)
        if to_group_result.is_err():
            raise HTTPException(status_code=404, detail="Target group not found")

        move_result = await group_service.move_file_between_groups(
            file_id, from_group_id, to_group_id
        )

        if move_result.is_err():
            error = move_result.unwrap_err()
            raise HTTPException(
                status_code=500, detail=f"Error moving file: {str(error)}"
            )

        return {
            "message": f"File {file_id} moved from {from_group_id} to {to_group_id}"
        }

    except HTTPException:
        raise
    except Exception as e:
        Logger.error(f"Unexpected error in move_file_between_groups: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{group_id}/stats")
@inject("group_service")
@inject("auth_service")
@inject("container_service")
async def get_group_stats(
    group_id: str,
    group_service: GroupService,
    auth_service: AuthService,
    container_service: ContainerService,
    request: Request,
):
    current_user = await get_current_user_from_request(request, auth_service)

    group_result = await group_service.get_group(group_id)
    if group_result.is_err():
        raise HTTPException(status_code=404, detail="Group not found")

    group = group_result.unwrap()

    container_result = await container_service.get_container(group.container_id)
    if container_result.is_err():
        raise HTTPException(status_code=404, detail="Container not found")

    container = container_result.unwrap()
    if container.user_id != str(current_user.tg_id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    stats_result = await group_service.get_group_stats(group_id)
    if stats_result.is_err():
        raise HTTPException(status_code=500, detail="Error fetching group statistics")

    stats = stats_result.unwrap()
    return {"data": stats}
