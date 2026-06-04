from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

import aiosqlite

from iso_robot.repositories.db import dumps_json


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ControlRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def delete_for_document(self, document_id: str) -> None:
        await self._conn.execute("DELETE FROM controls WHERE document_id = ?", (document_id,))
        await self._conn.commit()

    async def insert_many(
        self,
        rows: List[dict[str, Any]],
        client_org_id: Optional[str] = None,
    ) -> None:
        for r in rows:
            await self._conn.execute(
                """
                INSERT INTO controls (id, document_id, client_org_id, control_text, section_ref, framework, source_page, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r["id"],
                    r["document_id"],
                    r.get("client_org_id") or client_org_id,
                    r.get("control_text"),
                    r.get("section_ref"),
                    r.get("framework"),
                    r.get("source_page"),
                    r.get("created_at") or _now_iso(),
                ),
            )
        await self._conn.commit()

    async def list_all(
        self,
        *,
        limit: int = 500,
        offset: int = 0,
        document_id: Optional[str] = None,
        client_org_id: Optional[str] = None,
    ) -> List[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if document_id:
            clauses.append("document_id = ?")
            params.append(document_id)
        if client_org_id:
            clauses.append("client_org_id = ?")
            params.append(client_org_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])
        cur = await self._conn.execute(
            f"""
            SELECT id, document_id, client_org_id, control_text, section_ref, framework, source_page, created_at
            FROM controls
            {where}
            ORDER BY datetime(created_at) DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )
        rows = await cur.fetchall()
        return [dict(x) for x in rows]
    

    async def get_by_document(self, document_id: str) -> List[dict[str, Any]]:
        return await self.list_all(limit=10000, offset=0, document_id=document_id)
    
    async def stats_for_org(self, client_org_id: str) -> dict[str, int]:
        cur = await self._conn.execute(
            """
            SELECT COUNT(*) AS controls, COUNT(DISTINCT document_id) AS documents
            FROM controls WHERE client_org_id = ?
            """,
            (client_org_id,),
        )
        row = await cur.fetchone()
        return {"controls": row["controls"], "documents": row["documents"]}
