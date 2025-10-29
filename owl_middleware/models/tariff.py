from pydantic import BaseModel


class Tariff(BaseModel):
    memory_limit: int
    storage_qouta: int
    file_limit: int
