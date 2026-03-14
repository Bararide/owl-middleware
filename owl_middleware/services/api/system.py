from typing import Dict, Any
from fastbot.core import Result, result_try, Ok

from .client import ApiClient


class SystemHandler:
    def __init__(self, client: ApiClient):
        self.client = client

    @result_try
    async def health_check(self) -> Result[bool, Exception]:
        result = await self.client._make_request("GET", "/health")
        return Ok(result.is_ok())

    @result_try
    async def rebuild_index(self) -> Result[Dict[str, Any], Exception]:
        return await self.client._make_request("POST", "/rebuild")

    @result_try
    async def get_root(self) -> Result[Dict[str, Any], Exception]:
        return await self.client._make_request("GET", "/")
