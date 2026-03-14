import aiohttp
import json
from typing import Any, Optional, Dict
from fastbot.logger.logger import Logger
from fastbot.core import Result, result_try, Err, Ok


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    @result_try
    async def connect(self) -> Result[bool, Exception]:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                base_url=self.base_url,
                timeout=aiohttp.ClientTimeout(total=30),
                json_serialize=json.dumps,
            )
        return Ok(True)

    @result_try
    async def close(self) -> Result[bool, Exception]:
        if self.session and not self.session.closed:
            await self.session.close()
        return Ok(True)

    def _handle_response_status(
        self, status: int, data: Dict[str, Any]
    ) -> Result[Dict[str, Any], Exception]:
        status_handlers = {
            200: lambda: Ok(data),
            201: lambda: Ok(data),
            204: lambda: Ok({}),
            400: lambda: Err(ValueError(data.get("error", "Bad Request"))),
            401: lambda: Err(PermissionError("Unauthorized")),
            403: lambda: Err(PermissionError("Forbidden")),
            404: lambda: Err(FileNotFoundError(data.get("error", "Not Found"))),
            500: lambda: Err(
                Exception(f"Server Error: {data.get('error', 'Internal Server Error')}")
            ),
        }

        handler = status_handlers.get(status)
        if handler:
            return handler()

        return Err(
            Exception(f"HTTP error {status}: {data.get('error', 'Unknown error')}")
        )

    def _parse_response(
        self, response_text: str, status: int
    ) -> Result[Dict, Exception]:
        try:
            data = json.loads(response_text) if response_text else {}
            return self._handle_response_status(status, data)
        except json.JSONDecodeError as e:
            Logger.error(f"JSON decode error: {e}")
            return Err(Exception(f"Invalid JSON response: {response_text}"))

    def _extract_data(self, response_data: Dict) -> Result[Any, Exception]:
        if isinstance(response_data, dict) and "data" in response_data:
            return Ok(response_data["data"])
        return Ok(response_data)

    @result_try
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> Result[Any, Exception]:
        return (
            await (await self._ensure_connection())
            .and_then_async(
                lambda _: self._execute_request(
                    method, endpoint, json_data, params, headers
                )
            )
            .and_then_async(self._process_response)
        )

    @result_try
    async def _ensure_connection(self) -> Result[None, Exception]:
        """Гарантирует наличие соединения"""
        connect_result = await self.connect()
        return connect_result.map(lambda _: None)

    @result_try
    async def _execute_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict],
        params: Optional[Dict],
        headers: Optional[Dict],
    ) -> Result[aiohttp.ClientResponse, Exception]:
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)

        try:
            async with self.session.request(
                method=method,
                url=endpoint,
                json=json_data,
                params=params,
                headers=default_headers,
            ) as response:
                return Ok(response)
        except aiohttp.ClientError as e:
            Logger.error(f"HTTP client error: {e}")
            return Err(e)

    async def _process_response(
        self, response: aiohttp.ClientResponse
    ) -> Result[Any, Exception]:
        response_text = await response.text()

        return self._parse_response(response_text, response.status).and_then(
            self._extract_data
        )
