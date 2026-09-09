import os
import time
import hashlib
import uuid
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from fastapi import Header, HTTPException
from app.db import save_api_key_record, get_api_key_by_hash

logger = logging.getLogger("reelclaim.auth")

# Sliding window request timestamps per key_hash: Dict[key_hash, List[float]]
_request_timestamps: Dict[str, List[float]] = defaultdict(list)

# Fallback in-memory API key store when DB persistence is disabled: Dict[key_hash, dict]
_in_memory_keys: Dict[str, dict] = {}


DEFAULT_RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "60"))

def hash_key(raw_key: str) -> str:
    """Computes SHA-256 hash of a raw API key."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def register_new_api_key(name: str, rate_limit_per_hour: Optional[int] = None) -> Dict[str, str | int]:
    """
    Generates a new raw API key ('rc_live_<uuid_hex>'), hashes it, and persists it.
    Returns the raw key (shown only once) along with metadata.
    Default rate limit is 60 requests/hour (~1/min burst) tuned for small-scale users.
    """
    limit = rate_limit_per_hour if rate_limit_per_hour is not None else DEFAULT_RATE_LIMIT_PER_HOUR
    raw_key = f"rc_live_{uuid.uuid4().hex}"
    key_hash = hash_key(raw_key)

    # Save to database if available
    db_id = save_api_key_record(key_hash=key_hash, name=name, rate_limit_per_hour=limit)

    # Always keep in memory store as fallback/cache
    _in_memory_keys[key_hash] = {
        "id": db_id or str(uuid.uuid4()),
        "key_hash": key_hash,
        "name": name,
        "rate_limit_per_hour": limit,
        "is_active": True
    }

    return {
        "api_key": raw_key,
        "name": name,
        "rate_limit_per_hour": limit,
        "message": "Save this API key securely. It will not be shown again."
    }


def check_rate_limit(key_hash: str, rate_limit_per_hour: int):
    """
    In-process sliding window rate limiter (1-hour window).
    Raises HTTP 429 with Retry-After header if limit exceeded.
    """
    now = time.time()
    window_start = now - 3600.0

    timestamps = _request_timestamps[key_hash]
    # Keep only timestamps within the 1-hour window
    valid_timestamps = [t for t in timestamps if t > window_start]
    _request_timestamps[key_hash] = valid_timestamps

    if len(valid_timestamps) >= rate_limit_per_hour:
        oldest = valid_timestamps[0]
        retry_after = int(3600.0 - (now - oldest)) + 1
        if retry_after < 1:
            retry_after = 1

        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {rate_limit_per_hour} requests per hour. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )

    _request_timestamps[key_hash].append(now)


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Optional[Dict[str, str | int]]:
    """
    FastAPI dependency for API key authentication and sliding-window rate limiting.
    Bypasses checks when REQUIRE_AUTH environment variable is false/unset.
    """
    require_auth = os.getenv("REQUIRE_AUTH", "false").lower() in ("true", "1", "yes")
    if not require_auth:
        return None

    if not x_api_key or not x_api_key.strip():
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-API-Key header"
        )

    raw_key = x_api_key.strip()
    key_hash = hash_key(raw_key)

    # 1. Check database first
    key_info = get_api_key_by_hash(key_hash)

    # 2. Check in-memory store if DB lookup returns None
    if not key_info and key_hash in _in_memory_keys:
        mem = _in_memory_keys[key_hash]
        if mem.get("is_active", True):
            key_info = mem

    if not key_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid or inactive API key"
        )

    # Rate limiting check
    check_rate_limit(key_info["key_hash"], int(key_info["rate_limit_per_hour"]))

    return key_info


def reset_rate_limits():
    """Helper to clear rate limit timestamps during testing."""
    global _request_timestamps
    _request_timestamps.clear()
