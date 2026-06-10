from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, List, Optional

import aiosqlite

from iso_robot.repositories.db import dumps_json


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _loads_json(raw: Any) -> Any:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


class IssueRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def insert(
        self,
        *,
        issue_id: str,
        risk_source_id: Optional[str],
        title: Optional[str],
        body: Optional[str],
        effective_date: Optional[str] = None,
        region_hint: Optional[str] = None,
        raw_payload: Optional[dict[str, Any]] = None,
        client_org_id: Optional[str] = None,
    ) -> None:
        await self._conn.execute(
            """
            INSERT INTO issues (id, risk_source_id, title, body, effective_date, region_hint, raw_payload_json, client_org_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                issue_id,
                risk_source_id,
                title,
                body,
                effective_date,
                region_hint,
                dumps_json(raw_payload or {}),
                client_org_id,
                _now_iso(),
            ),
        )
        await self._conn.commit()

    async def upsert(
        self,
        *,
        issue_id: str,
        risk_source_id: Optional[str],
        title: Optional[str],
        body: Optional[str],
        effective_date: Optional[str] = None,
        region_hint: Optional[str] = None,
        raw_payload: Optional[dict[str, Any]] = None,
    ) -> None:
        await self._conn.execute(
            """
            INSERT INTO issues (id, risk_source_id, title, body, effective_date, region_hint, raw_payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              risk_source_id = excluded.risk_source_id,
              title = excluded.title,
              body = excluded.body,
              effective_date = COALESCE(excluded.effective_date, effective_date),
              region_hint = COALESCE(excluded.region_hint, region_hint),
              raw_payload_json = excluded.raw_payload_json
            """,
            (
                issue_id,
                risk_source_id,
                title,
                body,
                effective_date,
                region_hint,
                dumps_json(raw_payload or {}),
                _now_iso(),
            ),
        )
        await self._conn.commit()

    async def delete_derived_from_document(self, document_id: str, *, origin: str = "from_controls") -> int:
        cur = await self._conn.execute(
            """
            DELETE FROM issues
            WHERE json_extract(raw_payload_json, '$.source_document_id') = ?
              AND json_extract(raw_payload_json, '$.origin') = ?
            """,
            (document_id, origin),
        )
        await self._conn.commit()
        return int(cur.rowcount or 0)

    async def delete_derived_for_org(self, client_org_id: str, *, origin: str = "from_controls") -> int:
        cur = await self._conn.execute(
            """
            DELETE FROM issues
            WHERE client_org_id = ?
              AND json_extract(raw_payload_json, '$.origin') = ?
            """,
            (client_org_id, origin),
        )
        await self._conn.commit()
        return int(cur.rowcount or 0)

    async def list_all(
        self,
        limit: int = 2000,
        offset: int = 0,
        source_document_id: Optional[str] = None,
        client_org_id: Optional[str] = None,
    ) -> List[dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if source_document_id:
            clauses.append("json_extract(raw_payload_json, '$.source_document_id') = ?")
            params.append(source_document_id)
        if client_org_id:
            clauses.append("client_org_id = ?")
            params.append(client_org_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])
        cur = await self._conn.execute(
            f"""
            SELECT id, risk_source_id, title, body, effective_date, region_hint, raw_payload_json, client_org_id, created_at
            FROM issues
            {where}
            ORDER BY datetime(created_at) DESC
            LIMIT ? OFFSET ?
            """,
            params,
        )
        rows = await cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["raw_payload"] = _loads_json(d.pop("raw_payload_json", None))
            out.append(d)
        return out

    async def get_by_id(self, issue_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT id, risk_source_id, title, body, effective_date, region_hint, raw_payload_json, client_org_id, created_at
            FROM issues WHERE id = ?
            """,
            (issue_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["raw_payload"] = _loads_json(d.pop("raw_payload_json", None))
        return d

    async def list_ids_missing_classification(self) -> List[str]:
        cur = await self._conn.execute(
            """
            SELECT i.id FROM issues i
            LEFT JOIN issue_classifications c ON c.issue_id = i.id
            WHERE c.id IS NULL
            ORDER BY datetime(i.created_at) DESC
            """
        )
        rows = await cur.fetchall()
        return [str(r[0]) for r in rows]

    async def list_by_ids(self, issue_ids: List[str]) -> List[dict[str, Any]]:
        if not issue_ids:
            return []
        placeholders = ",".join("?" for _ in issue_ids)
        cur = await self._conn.execute(
            f"""
            SELECT id, risk_source_id, title, body, effective_date, region_hint, raw_payload_json, created_at
            FROM issues WHERE id IN ({placeholders})
            """,
            issue_ids,
        )
        rows = await cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["raw_payload"] = _loads_json(d.pop("raw_payload_json", None))
            out.append(d)
        return out
    
    async def stats_for_org(self, client_org_id: str) -> dict[str, int]:
        cur = await self._conn.execute(
            """
            SELECT COUNT(*) AS issues,
                   COUNT(DISTINCT json_extract(raw_payload_json, '$.source_document_id')) AS documents
            FROM issues WHERE client_org_id = ?
            """,
            (client_org_id,),
        )
        row = await cur.fetchone()
        return {"issues": row["issues"], "documents": row["documents"]}


class IssueClassificationRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def delete_for_issue(self, issue_id: str) -> None:
        await self._conn.execute("DELETE FROM issue_classifications WHERE issue_id = ?", (issue_id,))
        await self._conn.commit()

    async def insert(
        self,
        *,
        row_id: str,
        issue_id: str,
        classification: dict[str, Any],
        model_version: Optional[str] = None,
    ) -> None:
        await self._conn.execute(
            """
            INSERT INTO issue_classifications (id, issue_id, classification_json, model_version, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (row_id, issue_id, dumps_json(classification), model_version, _now_iso()),
        )
        await self._conn.commit()

    async def get_latest_for_issue(self, issue_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT id, issue_id, classification_json, model_version, created_at
            FROM issue_classifications
            WHERE issue_id = ?
            ORDER BY datetime(created_at) DESC
            LIMIT 1
            """,
            (issue_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["classification"] = _loads_json(d.pop("classification_json", None))
        return d

    async def map_for_issues(self, issue_ids: List[str]) -> dict[str, dict[str, Any]]:
        if not issue_ids:
            return {}
        placeholders = ",".join("?" for _ in issue_ids)
        cur = await self._conn.execute(
            f"""
            SELECT issue_id, classification_json, model_version, created_at
            FROM issue_classifications
            WHERE issue_id IN ({placeholders})
            ORDER BY issue_id, datetime(created_at) DESC
            """,
            issue_ids,
        )
        rows = await cur.fetchall()
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            iid = str(r[0])
            if iid in out:
                continue
            out[iid] = {
                "classification": _loads_json(r[1]),
                "model_version": r[2],
                "created_at": r[3],
            }
        return out
