from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from iso_robot.config import Settings

logger = logging.getLogger(__name__)

_client: Optional[Any] = None
_client_key: Optional[tuple[str, str, str]] = None
_lock = threading.Lock()


def get_milvus_client(settings: Settings) -> Optional[Any]:
    """Return a cached pymilvus ``MilvusClient``, or ``None`` when Milvus is not
    configured or currently unreachable.

    Mirrors :func:`iso_robot.integrations.azure_openai.get_azure_openai_client`:
    callers MUST treat ``None`` as "vector features disabled" and degrade
    gracefully. A failed connection is not cached, so a later call retries once
    Milvus becomes available.
    """
    uri = (settings.milvus_uri or "").strip()
    if not uri:
        return None

    global _client, _client_key
    key = (uri, settings.milvus_token or "", settings.milvus_db_name or "default")
    if _client is not None and _client_key == key:
        return _client

    with _lock:
        if _client is not None and _client_key == key:
            return _client
        try:
            from pymilvus import MilvusClient

            client = MilvusClient(
                uri=uri,
                token=settings.milvus_token or None,
                db_name=settings.milvus_db_name or "default",
            )
            _client = client
            _client_key = key
            logger.info("Connected to Milvus at %s (db=%s)", uri, key[2])
            return _client
        except Exception:  # noqa: BLE001 — connection issues must not crash callers
            logger.exception("Failed to connect to Milvus at %s; vector features disabled", uri)
            return None


def reset_milvus_client() -> None:
    """Drop the cached client (used by tests or after a config change)."""
    global _client, _client_key
    with _lock:
        _client = None
        _client_key = None
