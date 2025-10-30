from pydantic import BaseModel


class Tariff(BaseModel):
    memory_limit: int
    storage_quota: int
    file_limit: int
