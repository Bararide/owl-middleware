import aiofiles
import asyncio
import os
import json

from asyncio import Future
from typing import List

from fastbot.core import Result, result_try, Err, Ok


class ParserService:
    def __init__(self):
        pass

    @result_try
    async def parse(text: str) -> Result[Future[List[str]]]:
        pass
