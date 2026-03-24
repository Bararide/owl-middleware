from fastapi import HTTPException
from typing import Optional


class BusinessError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def unwrap_or_http(result, status_code: int = 500, detail: Optional[str] = None):
    if result.is_err():
        raise HTTPException(
            status_code=status_code, detail=detail or str(result.unwrap_err())
        )
    return result.unwrap()
