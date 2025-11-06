from fastbot.core import Result, result_try, Err, Ok
from pydantic import BaseModel, Field, field_validator

import fitz
import base64


class TextServiceConfig(BaseModel):
    max_file_size: int = Field(gt=0, description="Max file size must be positive")

    @field_validator("max_file_size")
    def validate_max_file_size(cls, v):
        if v > 100 * 1024 * 1024:
            raise ValueError("File size too large")
        return v


class TextService:
    def __init__(self, max_file_size: int):
        self._config = TextServiceConfig(max_file_size=max_file_size)

    @result_try
    async def extract_text_from_pdf(file) -> Result[str, Exception]:
        text = ""
        try:
            with fitz.open(file) as doc:
                for page in doc:
                    text += page.get_text()
            return Ok(text)
        except Exception as e:
            return Err(e)

    @property
    def max_file_size(self) -> int:
        return self._config.max_file_size

    @max_file_size.setter
    def max_file_size(self, value: int):
        self._config = TextServiceConfig(max_file_size=value)
