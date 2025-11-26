from deepseek_ocr import DeepSeekOCR
from fastbot.core import result_try, Ok, Err
import aiofiles
import os
from typing import Union, BinaryIO, Dict, Any


class Ocr:
    def __init__(self, api_key: str = None, base_url: str = None):
        self._ocr = DeepSeekOCR(api_key=api_key, base_url=base_url)

    @property
    def ocr(self) -> DeepSeekOCR:
        return self._ocr

    @result_try
    async def extract(self, document: Union[str, BinaryIO]) -> str:
        result = await self._ocr(document)

        if hasattr(result, "text"):
            return result.text
        elif isinstance(result, str):
            return result
        elif isinstance(result, dict):
            return result.get("text", "") or result.get("content", "")
        else:
            return str(result)

    @result_try
    async def extract_from_path(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        return await self.extract(file_path)

    @result_try
    async def extract_from_bytes(
        self, file_data: bytes, filename: str = "document"
    ) -> str:
        temp_path = f"/tmp/{filename}"
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(file_data)

        try:
            result = await self.extract(temp_path)
            return result
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    async def close(self):
        if hasattr(self._ocr, "close"):
            await self._ocr.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
