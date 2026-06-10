from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, List, Optional

import aiosqlite

from iso_robot.repositories.db import dumps_json


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class JobRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(
        self,
        *,
        job_id: str,
        job_type: str,
        status: str,
        payload: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        now = _now_iso()
        payload_json = dumps_json(payload)
        await self._conn.execute(
            """
            INSERT INTO jobs (id, type, status, payload_json, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, NULL, ?, ?)
            """,
            (job_id, job_type, status, payload_json, now, now),
        )
        await self._conn.commit()
        row = await self.get_by_id(job_id)
        if row is None:
            raise RuntimeError("Job row missing after insert")
        return row

    async def list_jobs(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[dict[str, Any]]:
        if status:
            cur = await self._conn.execute(
                """
                SELECT id, type, status, payload_json, error, created_at, updated_at
                FROM jobs
                WHERE status = ?
                ORDER BY datetime(created_at) DESC
                LIMIT ? OFFSET ?
                """,
                (status, limit, offset),
            )
        else:
            cur = await self._conn.execute(
                """
                SELECT id, type, status, payload_json, error, created_at, updated_at
                FROM jobs
                ORDER BY datetime(created_at) DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        rows = await cur.fetchall()
        return [_row_to_job(dict(r)) for r in rows]

    async def get_by_id(self, job_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT id, type, status, payload_json, error, created_at, updated_at
            FROM jobs WHERE id = ?
            """,
            (job_id,),
        )
        row = await cur.fetchone()
        return _row_to_job(dict(row)) if row else None

    async def update_status(
        self,
        job_id: str,
        *,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        now = _now_iso()
        await self._conn.execute(
            """
            UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE id = ?
            """,
            (status, error, now, job_id),
        )
        await self._conn.commit()

    async def merge_payload(self, job_id: str, updates: dict[str, Any]) -> None:
        """Shallow-merge keys into the job payload (e.g. progress while running)."""
        row = await self.get_by_id(job_id)
        if row is None:
            return
        payload = dict(row.get("payload") or {})
        payload.update(updates)
        now = _now_iso()
        await self._conn.execute(
            """
            UPDATE jobs SET payload_json = ?, updated_at = ? WHERE id = ?
            """,
            (dumps_json(payload), now, job_id),
        )
        await self._conn.commit()


def _row_to_job(row: dict[str, Any]) -> dict[str, Any]:
    payload_raw = row.get("payload_json") or "{}"
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        payload = {}
    return {
        "id": row["id"],
        "type": row["type"],
        "status": row["status"],
        "payload": payload,
        "error": row.get("error"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
