import aiofiles
import asyncio
import os
import aiohttp
import json

from typing import Dict, List, Any, Optional
from fastbot.logger.logger import Logger
from pampy import _, match

from models import File, User, Tariff, Label, Container
from fastbot.core import Result, result_try, Err, Ok


class ApiService:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _handle_response(self, response: aiohttp.ClientResponse, result: Any) -> Result:
        return match(
            response.status,
            200,
            Ok(result),
            201,
            Ok(result),
            204,
            Ok({}),
            400,
            Err(ValueError(result.get("error", "Bad Request"))),
            401,
            Err(PermissionError("Unauthorized")),
            403,
            Err(PermissionError("Forbidden")),
            404,
            Err(FileNotFoundError(result.get("error", "Not Found"))),
            500,
            Err(
                Exception(
                    f"Server Error: {result.get('error', 'Internal Server Error')}"
                )
            ),
            _,
            Err(
                Exception(
                    f"HTTP error {response.status}: {result.get('error', 'Unknown error')}"
                )
            ),
        )

    async def connect(self) -> Result[bool, Exception]:
        try:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession(
                    base_url=self.base_url,
                    timeout=aiohttp.ClientTimeout(total=30),
                    json_serialize=json.dumps,
                )
            return Ok(True)
        except Exception as e:
            return Err(e)

    async def close(self) -> Result[bool, Exception]:
        try:
            if self.session and not self.session.closed:
                await self.session.close()
            return Ok(True)
        except Exception as e:
            return Err(e)

    @result_try
    async def get_files_by_container_id(
        self,
        user_id: str,
        container_id: str,
    ) -> Result[List[Dict[str, Any]], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        payload = {
            "user_id": str(user_id),
            "container_id": str(container_id),
        }

        try:
            async with self.session.get(
                "/container/files",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                response_text = await response.text()

                try:
                    data = json.loads(response_text)

                    if response.status == 200:
                        if "data" in data:
                            files_data = data["data"]
                            if "files" in files_data:
                                return Ok(files_data["files"])
                            else:
                                return Ok([])
                        else:
                            return Ok([])
                    else:
                        error_msg = data.get("error", f"HTTP error {response.status}")
                        return Err(Exception(error_msg))

                except json.JSONDecodeError as e:
                    Logger.error(f"JSON decode error: {e}")
                    Logger.error(f"Response text that failed to parse: {response_text}")
                    return Err(Exception(f"Invalid JSON response: {response_text}"))
        except aiohttp.ClientError as e:
            Logger.error(f"HTTP client error: {e}")
            return Err(e)
        except Exception as e:
            Logger.error(f"Unexpected error in get_files_by_container_id: {e}")
            return Err(e)

    @result_try
    async def delete_file(
        self, user_id: str, container_id: str, file_id: str
    ) -> Result[bool, Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        payload = {"user_id": user_id, "container_id": container_id, "file_id": file_id}

        try:
            async with self.session.delete(
                f"/files/delete",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:

                response_text = await response.text()
                try:
                    data = json.loads(response_text)

                    if response.status == 200:
                        if "data" in data:
                            container_data = data["data"]
                            if container_data.get("status") in [
                                "deleted",
                                "deletion_pending",
                            ]:
                                return Ok(True)
                            else:
                                return Ok(False)
                        else:
                            return Ok(True)
                    else:
                        error_msg = data.get("error", f"HTTP error {response.status}")
                        return Err(Exception(error_msg))

                except json.JSONDecodeError as e:
                    Logger.error(f"JSON decode error: {e}")
                    Logger.error(f"Response text that failed to parse: {response_text}")
                    return Err(Exception(f"Invalid JSON response: {response_text}"))

        except aiohttp.ClientError as e:
            Logger.error(f"HTTP client error: {e}")
            return Err(e)
        except Exception as e:
            Logger.error(f"Unexpected error in delete_container: {e}")
            return Err(e)

    @result_try
    async def delete_container(
        self, user_id: str, container_id: str
    ) -> Result[bool, Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        payload = {
            "user_id": str(user_id),
            "container_id": str(container_id),
        }

        try:
            async with self.session.delete(
                f"/containers/delete",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:

                response_text = await response.text()
                # Logger.info(f"Raw response text: {response_text}")

                try:
                    data = json.loads(response_text)
                    # Logger.info(f"Parsed JSON data: {data}")

                    if response.status == 200:
                        if "data" in data:
                            container_data = data["data"]
                            if container_data.get("status") in [
                                "deleted",
                                "deletion_pending",
                            ]:
                                return Ok(True)
                            else:
                                return Ok(False)
                        else:
                            return Ok(True)
                    else:
                        error_msg = data.get("error", f"HTTP error {response.status}")
                        return Err(Exception(error_msg))

                except json.JSONDecodeError as e:
                    Logger.error(f"JSON decode error: {e}")
                    Logger.error(f"Response text that failed to parse: {response_text}")
                    return Err(Exception(f"Invalid JSON response: {response_text}"))

        except aiohttp.ClientError as e:
            Logger.error(f"HTTP client error: {e}")
            return Err(e)
        except Exception as e:
            Logger.error(f"Unexpected error in delete_container: {e}")
            return Err(e)

    @result_try
    async def create_container(
        self,
        user_id: str,
        container_id: str,
        tariff: Tariff,
        env_label: Label,
        type_label: Label,
        commands: List[str],
        privileged: bool,
    ) -> Result[Dict[str, Any], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        payload = {
            "user_id": user_id,
            "container_id": container_id,
            "memory_limit": tariff.memory_limit,
            "storage_quota": tariff.storage_quota,
            "file_limit": tariff.file_limit,
            "env_label": {"key": env_label.key, "value": env_label.value},
            "type_label": {"key": type_label.key, "value": type_label.value},
            "commands": commands,
            "privileged": privileged,
        }

        try:
            async with self.session.post(
                "/containers/create",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:

                response_text = await response.text()
                # Logger.info(f"Raw response text: {response_text}")

                try:
                    data = json.loads(response_text)
                    # Logger.info(f"Parsed JSON data: {data}")

                    if response.status == 200:
                        if "data" in data:
                            return Ok(data["data"])
                        else:
                            return Ok(data)
                    else:
                        error_msg = data.get("error", f"HTTP error {response.status}")
                        return Err(Exception(error_msg))

                except json.JSONDecodeError as e:
                    Logger.error(f"JSON decode error: {e}")
                    Logger.error(f"Response text that failed to parse: {response_text}")
                    return Err(Exception(f"Invalid JSON response: {response_text}"))

        except aiohttp.ClientError as e:
            Logger.error(f"HTTP client error: {e}")
            return Err(e)
        except Exception as e:
            Logger.error(f"Unexpected error in create_container: {e}")
            return Err(e)

    @result_try
    async def create_file(
        self, path: str, content: str, user_id: str, container_id: str
    ) -> Result[Dict[str, Any], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        payload = {
            "path": path,
            "content": content,
            "user_id": user_id,
            "container_id": container_id,
        }

        try:
            async with self.session.post(
                "/files/create",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:

                response_text = await response.text()
                Logger.info(f"Raw response for file create: {response_text}")
                Logger.info(f"Response status: {response.status}")
                Logger.info(f"Response headers: {dict(response.headers)}")

                content_size = len(content)
                Logger.info(f"File content size: {content_size} bytes")

                if response.status == 413:
                    return Err(Exception(f"File too large: {content_size} bytes"))

                try:
                    data = json.loads(response_text)

                    if response.status in [200, 201]:
                        if "data" in data:
                            return Ok(data["data"])
                        else:
                            return Ok(data)
                    else:
                        error_msg = data.get("error", f"HTTP error {response.status}")
                        return Err(Exception(error_msg))

                except json.JSONDecodeError as e:
                    Logger.error(f"JSON decode error: {e}")
                    Logger.error(f"Response text that failed to parse: {response_text}")
                    return Err(Exception(f"Invalid JSON response: {response_text}"))

        except aiohttp.ClientError as e:
            Logger.error(f"HTTP client error: {e}")
            return Err(e)
        except Exception as e:
            Logger.error(f"Unexpected error in create_file: {e}")
            return Err(e)

    @result_try
    async def semantic_search(
        self, query: str, user: User, container: Container, limit: int = 5
    ) -> Result[Dict[str, Any], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        Logger.info(container.id)

        payload = {
            "query": query,
            "limit": limit,
            "user_id": str(user.id),
            "container_id": str(container.id),
        }

        try:
            async with self.session.post(
                "/containers/semantic",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                # Logger.info(f"Semantic search response: {response.status}")

                response_text = await response.text()
                # Logger.info(f"Raw response text: {response_text}")
                # Logger.info(f"Response headers: {dict(response.headers)}")

                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        if "data" in data:
                            return Ok(data["data"])
                        else:
                            return Ok(data)
                    except json.JSONDecodeError as e:
                        Logger.error(f"JSON decode error: {e}")
                        return Err(Exception(f"Invalid JSON response: {response_text}"))
                else:
                    try:
                        error_data = json.loads(response_text)
                        error_msg = error_data.get(
                            "error", f"HTTP error {response.status}"
                        )
                    except:
                        error_msg = f"HTTP error {response.status}: {response_text}"

                    Logger.error(f"Semantic search failed: {error_msg}")
                    return Err(Exception(error_msg))

        except aiohttp.ClientError as e:
            Logger.error(f"HTTP client error: {e}")
            return Err(e)
        except Exception as e:
            Logger.error(f"Unexpected error in semantic_search: {e}")
            return Err(e)

    @result_try
    async def read_file(self, path: str) -> Result[Dict[str, Any], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        # Logger.error(f"{path}")

        params = {"path": path}

        try:
            async with self.session.get("/files/read", params=params) as response:
                data = await response.json()
                return self._handle_response(response, data)
        except aiohttp.ClientError as e:
            return Err(e)
        except json.JSONDecodeError as e:
            return Err(Exception(f"Invalid JSON response: {e}"))

    @result_try
    async def rebuild_index(self) -> Result[Dict[str, Any], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        try:
            async with self.session.post("/rebuild") as response:
                data = await response.json()
                return self._handle_response(response, data)
        except aiohttp.ClientError as e:
            return Err(e)
        except json.JSONDecodeError as e:
            return Err(Exception(f"Invalid JSON response: {e}"))

    @result_try
    async def get_file_content(
        self, file_id: str, container_id: str
    ) -> Result[str, Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        payload = {"file_id": str(file_id), "container_id": str(container_id)}

        try:
            async with self.session.get(
                "/files/read",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    if isinstance(data, dict):
                        if "data" in data:
                            content = data["data"]
                            if isinstance(content, dict):
                                if "content" in content:
                                    return Ok(str(content["content"]))
                                elif "text" in content:
                                    return Ok(str(content["text"]))
                                else:
                                    return Ok(str(content))
                            else:
                                return Ok(str(content))
                        else:
                            if "content" in data:
                                return Ok(str(data["content"]))
                            elif "text" in data:
                                return Ok(str(data["text"]))
                            else:
                                return Ok(str(data))
                    else:
                        return Ok(str(data))
                else:
                    error_data = await response.json()
                    error_msg = error_data.get("error", f"HTTP error {response.status}")
                    return Err(Exception(error_msg))
        except aiohttp.ClientError as e:
            return Err(e)
        except json.JSONDecodeError as e:
            return Err(Exception(f"Invalid JSON response: {e}"))

    @result_try
    async def get_root(self) -> Result[Dict[str, Any], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        try:
            async with self.session.get("/") as response:
                data = await response.json()
                return self._handle_response(response, data)
        except aiohttp.ClientError as e:
            return Err(e)
        except json.JSONDecodeError as e:
            return Err(Exception(f"Invalid JSON response: {e}"))

    @result_try
    async def upload_file(
        self, local_path: str, remote_path: str
    ) -> Result[Dict[str, Any], Exception]:
        try:
            async with aiofiles.open(local_path, "r", encoding="utf-8") as f:
                content = await f.read()

            return await self.create_file(remote_path, content)

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

        content_data = read_result.unwrap()
        content = content_data.get("content", "")

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
    async def health_check(self) -> Result[bool, Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        try:
            async with self.session.get("/health", timeout=5) as response:
                return Ok(response.status == 200)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return Err(e)

    @result_try
    async def create_file_from_model(
        self, file: File, content: str
    ) -> Result[Dict[str, Any], Exception]:
        path = f"/{file.id}_{file.name}" if file.name else f"/{file.id}"
        return await self.create_file(path, content)
