import aiofiles
import asyncio
import os
import aiohttp
from typing import Dict, List, Any, Optional
import json

from models import File, User
from fastbot.core import Result, result_try, Err, Ok


class ApiService:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self):
        await self.close()

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
    async def create_file(
        self, path: str, content: str
    ) -> Result[Dict[str, Any], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        payload = {"path": path, "content": content}

        try:
            async with self.session.post("/files/create", json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return Ok(data)
                else:
                    error_data = await response.json()
                    error_msg = error_data.get("error", f"HTTP error {response.status}")
                    return Err(Exception(error_msg))
        except aiohttp.ClientError as e:
            return Err(e)

    @result_try
    async def read_file(self, path: str) -> Result[Dict[str, Any], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        params = {"path": path}

        try:
            async with self.session.get("/files/read", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return Ok(data)
                elif response.status == 404:
                    return Err(FileNotFoundError(f"File not found: {path}"))
                else:
                    error_data = await response.json()
                    error_msg = error_data.get("error", f"HTTP error {response.status}")
                    return Err(Exception(error_msg))
        except aiohttp.ClientError as e:
            return Err(e)

    @result_try
    async def semantic_search(
        self, query: str, limit: int = 5
    ) -> Result[Dict[str, Any], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        payload = {"query": query, "limit": limit}

        try:
            async with self.session.post("/semantic", json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return Ok(data)
                else:
                    error_data = await response.json()
                    error_msg = error_data.get("error", f"HTTP error {response.status}")
                    return Err(Exception(error_msg))
        except aiohttp.ClientError as e:
            return Err(e)

    @result_try
    async def rebuild_index(self) -> Result[Dict[str, Any], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        try:
            async with self.session.post("/rebuild") as response:
                if response.status == 200:
                    data = await response.json()
                    return Ok(data)
                else:
                    error_data = await response.json()
                    error_msg = error_data.get("error", f"HTTP error {response.status}")
                    return Err(Exception(error_msg))
        except aiohttp.ClientError as e:
            return Err(e)

    @result_try
    async def get_root(self) -> Result[Dict[str, Any], Exception]:
        connect_result = await self.connect()
        if connect_result.is_err():
            return connect_result

        try:
            async with self.session.get("/") as response:
                if response.status == 200:
                    data = await response.json()
                    return Ok(data)
                else:
                    error_data = await response.json()
                    error_msg = error_data.get("error", f"HTTP error {response.status}")
                    return Err(Exception(error_msg))
        except aiohttp.ClientError as e:
            return Err(e)

    @result_try
    async def upload_file(
        self, local_path: str, remote_path: str
    ) -> Result[Dict[str, Any], Exception]:
        try:
            async with aiofiles.open(local_path, "r", encoding="utf-8") as f:
                content = await f.read()

            return await self.create_file(remote_path, content)

        except FileNotFoundError as e:
            return Err(e)
        except Exception as e:
            return Err(e)

    @result_try
    async def download_file(
        self, remote_path: str, local_path: str
    ) -> Result[Dict[str, Any], Exception]:
        read_result = await self.read_file(remote_path)

        if read_result.is_err():
            return read_result

        content = read_result.unwrap().get("content", "")

        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            async with aiofiles.open(local_path, "w", encoding="utf-8") as f:
                await f.write(content)

            return Ok(
                {
                    "message": f"File downloaded successfully to {local_path}",
                    "size": len(content),
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
            async with self.session.get("/", timeout=5) as response:
                return Ok(response.status == 200)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return Err(e)

    @result_try
    async def create_file_from_model(
        self, file: File, content: str
    ) -> Result[Dict[str, Any], Exception]:
        path = f"/{file.id}_{file.name}" if file.name else f"/{file.id}"

        return await self.create_file(path, content)

    @result_try
    async def get_files_for_user(
        self, user: User
    ) -> Result[List[Dict[str, Any]], Exception]:
        search_query = f"user:{user.id} {user.username if user.username else ''}"

        search_result = await self.semantic_search(search_query, limit=100)

        if search_result.is_err():
            return search_result

        files_data = search_result.unwrap().get("results", [])
        return Ok(files_data)
