import aiofiles
import os
from typing import Dict, Any
from fastbot.core import Result, result_try, Ok, Err
from fastbot.logger.logger import Logger
from models import File

from .client import ApiClient


class FileHandler:
    def __init__(self, client: ApiClient):
        self.client = client

    @result_try
    async def delete_file(
        self, user_id: str, container_id: str, file_id: str
    ) -> Result[bool, Exception]:
        payload = {"user_id": user_id, "container_id": container_id, "file_id": file_id}

        result = await self.client._make_request(
            "DELETE", "/files/delete", json_data=payload
        )

        if result.is_ok():
            data = result.unwrap()
            if isinstance(data, dict):
                status = data.get("status")
                return Ok(status in ["deleted", "deletion_pending"])
            return Ok(True)

        return result

    @result_try
    async def create_file(
        self, path: str, content: str, user_id: str, container_id: str
    ) -> Result[Dict[str, Any], Exception]:
        payload = {
            "path": path,
            "content": content,
            "user_id": user_id,
            "container_id": container_id,
        }

        return await self.client._make_request(
            "POST", "/files/create", json_data=payload
        )

    @result_try
    async def read_file(self, path: str) -> Result[Dict[str, Any], Exception]:
        params = {"path": path}
        return await self.client._make_request("GET", "/files/read", params=params)

    @result_try
    async def get_file_content(
        self, file_id: str, container_id: str
    ) -> Result[tuple[str, str | None], Exception]:
        payload = {"file_id": str(file_id), "container_id": str(container_id)}

        result = await self.client._make_request(
            "GET", "/files/read", json_data=payload
        )

        if result.is_ok():
            data = result.unwrap()
            content = ""
            explanation = None

            if isinstance(data, dict):
                if "data" in data:
                    content_data = data["data"]
                    if isinstance(content_data, dict):
                        content = str(content_data.get("content", ""))
                        explanation = str(content_data.get("explanation"))
                    else:
                        content = str(content_data)
                else:
                    content = str(data.get("content", ""))
                    explanation = str(data.get("explanation"))
            else:
                content = str(data)

            return Ok((content, explanation))

        return result

    @result_try
    async def upload_file(
        self, local_path: str, remote_path: str, user_id: str, container_id: str
    ) -> Result[Dict[str, Any], Exception]:
        try:
            async with aiofiles.open(local_path, "r", encoding="utf-8") as f:
                content = await f.read()

            return await self.create_file(remote_path, content, user_id, container_id)

        except FileNotFoundError as e:
            return Err(FileNotFoundError(f"Local file not found: {local_path}"))
        except Exception as e:
            return Err(e)

    @result_try
    async def download_file(
        self, remote_path: str, local_path: str
    ) -> Result[Dict[str, Any], Exception]:
        read_result = await self.read_file(remote_path)

        if read_result.is_err():
            return read_result

        data = read_result.unwrap()
        content = ""

        if isinstance(data, dict):
            content = data.get("content", data.get("text", ""))
        else:
            content = str(data)

        if not content:
            return Err(ValueError("File content is empty"))

        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            async with aiofiles.open(local_path, "w", encoding="utf-8") as f:
                await f.write(content)

            return Ok(
                {
                    "message": f"File downloaded successfully to {local_path}",
                    "size": len(content),
                    "path": local_path,
                }
            )

        except Exception as e:
            return Err(e)

    @result_try
    async def create_file_from_model(
        self, file: File, content: str
    ) -> Result[Dict[str, Any], Exception]:
        path = f"/{file.id}_{file.name}" if file.name else f"/{file.id}"
        return await self.create_file(
            path, content, str(int(file.user_id) + 1), file.container_id
        )
