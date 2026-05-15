from typing import Any, Dict, List, Set, Union, Optional
from fastbot.logger import Logger
from fastbot.core import Result, result_try, Err, Ok
import redis.asyncio as redis


class RedisService:
    def __init__(self, host: str, port: int, decode: bool):
        self.host = host
        self.port = port
        self.decode = decode
        self.client: Optional[redis.Redis] = None

    @result_try
    async def connect(self) -> Result[bool, Exception]:
        if self.client is None:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                decode_responses=self.decode,
            )
            await self.client.ping()
            Logger.info(f"Connected to Redis at {self.host}:{self.port}")
        return Ok(True)

    @result_try
    async def close(self) -> Result[bool, Exception]:
        if self.client is not None:
            await self.client.close()
            self.client = None
            Logger.info("Redis connection closed")
        return Ok(True)

    @result_try
    async def ping(self) -> Result[bool, Exception]:
        if self.client is None:
            await self.connect()
        res = await self.client.ping()
        return Ok(res)

    @result_try
    async def set(
        self, key: str, value: Any, ex: Optional[int] = None
    ) -> Result[bool, Exception]:
        if self.client is None:
            await self.connect()
        res = await self.client.set(key, value, ex=ex)
        Logger.debug(f"SET {key} = {value} (ex={ex})")
        return Ok(res is True or res == "OK")

    @result_try
    async def get(self, key: str) -> Result[Any, Exception]:
        if self.client is None:
            await self.connect()
        value = await self.client.get(key)
        Logger.debug(f"GET {key} -> {value}")
        return Ok(value)

    @result_try
    async def delete(self, *keys: str) -> Result[int, Exception]:
        if self.client is None:
            await self.connect()
        count = await self.client.delete(*keys)
        Logger.debug(f"DEL {keys} -> {count} deleted")
        return Ok(count)

    @result_try
    async def exists(self, *keys: str) -> Result[int, Exception]:
        if self.client is None:
            await self.connect()
        count = await self.client.exists(*keys)
        Logger.debug(f"EXISTS {keys} -> {count}")
        return Ok(count)

    @result_try
    async def expire(self, key: str, seconds: int) -> Result[bool, Exception]:
        if self.client is None:
            await self.connect()
        res = await self.client.expire(key, seconds)
        Logger.debug(f"EXPIRE {key} {seconds}s -> {res}")
        return Ok(res)

    @result_try
    async def hset(self, name: str, key: str, value: Any) -> Result[int, Exception]:
        if self.client is None:
            await self.connect()
        count = await self.client.hset(name, key, value)
        Logger.debug(f"HSET {name} {key} = {value}")
        return Ok(count)

    @result_try
    async def hget(self, name: str, key: str) -> Result[Any, Exception]:
        if self.client is None:
            await self.connect()
        value = await self.client.hget(name, key)
        Logger.debug(f"HGET {name} {key} -> {value}")
        return Ok(value)

    @result_try
    async def hgetall(self, name: str) -> Result[Dict[str, Any], Exception]:
        if self.client is None:
            await self.connect()
        data = await self.client.hgetall(name)
        Logger.debug(f"HGETALL {name} -> {len(data)} fields")
        return Ok(data)

    @result_try
    async def hdel(self, name: str, *keys: str) -> Result[int, Exception]:
        if self.client is None:
            await self.connect()
        count = await self.client.hdel(name, *keys)
        Logger.debug(f"HDEL {name} {keys} -> {count} deleted")
        return Ok(count)

    @result_try
    async def lpush(self, key: str, *values: Any) -> Result[int, Exception]:
        if self.client is None:
            await self.connect()
        length = await self.client.lpush(key, *values)
        Logger.debug(f"LPUSH {key} {values} -> new length {length}")
        return Ok(length)

    @result_try
    async def rpush(self, key: str, *values: Any) -> Result[int, Exception]:
        if self.client is None:
            await self.connect()
        length = await self.client.rpush(key, *values)
        Logger.debug(f"RPUSH {key} {values} -> new length {length}")
        return Ok(length)

    @result_try
    async def lpop(self, key: str) -> Result[Any, Exception]:
        if self.client is None:
            await self.connect()
        value = await self.client.lpop(key)
        Logger.debug(f"LPOP {key} -> {value}")
        return Ok(value)

    @result_try
    async def rpop(self, key: str) -> Result[Any, Exception]:
        if self.client is None:
            await self.connect()
        value = await self.client.rpop(key)
        Logger.debug(f"RPOP {key} -> {value}")
        return Ok(value)

    @result_try
    async def lrange(
        self, key: str, start: int, end: int
    ) -> Result[List[Any], Exception]:
        if self.client is None:
            await self.connect()
        items = await self.client.lrange(key, start, end)
        Logger.debug(f"LRANGE {key} {start}:{end} -> {len(items)} items")
        return Ok(items)

    # --- Set operations ---

    @result_try
    async def sadd(self, key: str, *values: Any) -> Result[int, Exception]:
        if self.client is None:
            await self.connect()
        added = await self.client.sadd(key, *values)
        Logger.debug(f"SADD {key} {values} -> {added} added")
        return Ok(added)

    @result_try
    async def srem(self, key: str, *values: Any) -> Result[int, Exception]:
        if self.client is None:
            await self.connect()
        removed = await self.client.srem(key, *values)
        Logger.debug(f"SREM {key} {values} -> {removed} removed")
        return Ok(removed)

    @result_try
    async def smembers(self, key: str) -> Result[Set[Any], Exception]:
        if self.client is None:
            await self.connect()
        members = await self.client.smembers(key)
        Logger.debug(f"SMEMBERS {key} -> {len(members)} members")
        return Ok(members)

    @result_try
    async def incr(self, key: str) -> Result[int, Exception]:
        if self.client is None:
            await self.connect()
        new_val = await self.client.incr(key)
        Logger.debug(f"INCR {key} -> {new_val}")
        return Ok(new_val)

    @result_try
    async def decr(self, key: str) -> Result[int, Exception]:
        if self.client is None:
            await self.connect()
        new_val = await self.client.decr(key)
        Logger.debug(f"DECR {key} -> {new_val}")
        return Ok(new_val)

    @result_try
    async def flushall(self) -> Result[bool, Exception]:
        if self.client is None:
            await self.connect()
        await self.client.flushall()
        Logger.info("FLUSHALL executed")
        return Ok(True)

    @result_try
    async def flushdb(self) -> Result[bool, Exception]:
        """Очищает текущую базу данных."""
        if self.client is None:
            await self.connect()
        await self.client.flushdb()
        Logger.info("FLUSHDB executed")
        return Ok(True)

    @result_try
    async def keys(self, pattern: str = "*") -> Result[List[str], Exception]:
        if self.client is None:
            await self.connect()
        key_list = await self.client.keys(pattern)
        Logger.debug(f"KEYS {pattern} -> {len(key_list)} keys")
        return Ok(key_list)
