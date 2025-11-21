import asyncio
import json

from models import User
from fastbot.core import Result, result_try, Err, Ok


class AgentService:
    def __init__(self):
        self._api_key = ""
        self._model = ""

    @property
    def api_key(self) -> str:
        return self._api_key

    @api_key.setter
    def api_key(self, value: str):
        self._api_key = value

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str):
        self._model = value
