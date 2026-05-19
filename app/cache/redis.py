"""Factory de clientes Redis."""

from __future__ import annotations

import redis


def create_redis_client(url: str) -> redis.Redis:
    return redis.from_url(url, decode_responses=True)
