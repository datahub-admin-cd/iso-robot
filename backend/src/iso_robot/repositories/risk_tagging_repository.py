from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from iso_robot.repositories.db import dumps_json

TAG_DIMENSIONS = ("process", "function", "department", "kpi", "region", "control_family")
TAG_STATUSES = ("proposed", "applied", "needs_review", "rejected")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _loads_json(raw: Any, default: Any) -> Any:
    if raw is None or raw == "":
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


def _row_to_risk_tag(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for dim in TAG_DIMENSIONS:
        out[f"{dim}_tags"] = _loads_json(out.pop(f"{dim}_tags_json", "[]"), [])
    out["evidence"] = _loads_json(out.pop("evidence_json", "[]"), [])
    out["inputs"] = _loads_json(out.pop("inputs_json", "{}"), {})
    return out


class CatalogRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def insert_items(self, items: List[dict[str, Any]]) -> int:
        now = _now_iso()
        for item in items:
            await self._conn.execute(
                """
                INSERT INTO catalog_items (
                  id, client_org_id, catalog_id, dimension, name, description,
                  keywords_json, criticality, owner_user_id, catalog_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("id") or str(uuid.uuid4()),
                    item["client_org_id"],
                    item["catalog_id"],
                    item["dimension"],
                    item["name"],
                    item.get("description"),
                    dumps_json(item.get("keywords") or []),
                    item.get("criticality") or "standard",
                    item.get("owner_user_id"),
                    item.get("catalog_version") or "v1",
                    now,
                ),
            )
        await self._conn.commit()
        return len(items)

    async def list_for_org(
        self,
        client_org_id: str,
        dimensions: Optional[List[str]] = None,
    ) -> List[dict[str, Any]]:
        if dimensions:
            placeholders = ",".join("?" for _ in dimensions)
            cur = await self._conn.execute(
                f"""
                SELECT * FROM catalog_items
                WHERE client_org_id = ? AND dimension IN ({placeholders})
                ORDER BY dimension, name
                """,
                (client_org_id, *dimensions),
            )
        else:
            cur = await self._conn.execute(
                "SELECT * FROM catalog_items WHERE client_org_id = ? ORDER BY dimension, name",
                (client_org_id,),
            )
        rows = await cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["keywords"] = _loads_json(d.pop("keywords_json", "[]"), [])
            out.append(d)
        return out

    async def get_items_by_ids(self, item_ids: List[str]) -> List[dict[str, Any]]:
        if not item_ids:
            return []
        placeholders = ",".join("?" for _ in item_ids)
        cur = await self._conn.execute(
            f"SELECT * FROM catalog_items WHERE id IN ({placeholders})",
            tuple(item_ids),
        )
        rows = await cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["keywords"] = _loads_json(d.pop("keywords_json", "[]"), [])
            out.append(d)
        return out

    async def catalog_ids_for_org(self, client_org_id: str) -> Dict[str, str]:
        cur = await self._conn.execute(
            "SELECT DISTINCT dimension, catalog_id FROM catalog_items WHERE client_org_id = ?",
            (client_org_id,),
        )
        rows = await cur.fetchall()
        return {str(r[0]): str(r[1]) for r in rows}

    async def has_items(self, client_org_id: str) -> bool:
        cur = await self._conn.execute(
            "SELECT 1 FROM catalog_items WHERE client_org_id = ? LIMIT 1",
            (client_org_id,),
        )
        return await cur.fetchone() is not None


class RiskTagRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def insert(
        self,
        *,
        client_org_id: str,
        risk_id: str,
        tags_by_dimension: Dict[str, List[dict[str, Any]]],
        tag_status: str,
        confidence: Optional[float],
        rationale: Optional[str],
        evidence: Optional[List[str]] = None,
        inputs: Optional[dict[str, Any]] = None,
        catalog_version: Optional[str] = None,
        run_job_id: Optional[str] = None,
        auto_applied: bool = False,
    ) -> dict[str, Any]:
        row_id = str(uuid.uuid4())
        now = _now_iso()
        await self._conn.execute(
            """
            INSERT INTO risk_tags (
              id, client_org_id, risk_id,
              process_tags_json, function_tags_json, department_tags_json,
              kpi_tags_json, region_tags_json, control_family_tags_json,
              tag_status, confidence, rationale, evidence_json, inputs_json,
              catalog_version, run_job_id, auto_applied, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id, client_org_id, risk_id,
                dumps_json(tags_by_dimension.get("process") or []),
                dumps_json(tags_by_dimension.get("function") or []),
                dumps_json(tags_by_dimension.get("department") or []),
                dumps_json(tags_by_dimension.get("kpi") or []),
                dumps_json(tags_by_dimension.get("region") or []),
                dumps_json(tags_by_dimension.get("control_family") or []),
                tag_status, confidence, rationale,
                dumps_json(evidence or []),
                dumps_json(inputs or {}),
                catalog_version, run_job_id, 1 if auto_applied else 0,
                now, now,
            ),
        )
        await self._conn.commit()
        return (await self.get_by_id(row_id))  # type: ignore[return-value]

    async def get_by_id(self, row_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute("SELECT * FROM risk_tags WHERE id = ?", (row_id,))
        row = await cur.fetchone()
        return _row_to_risk_tag(dict(row)) if row else None

    async def list_for_org(
        self,
        client_org_id: str,
        *,
        risk_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict[str, Any]]:
        sql = "SELECT * FROM risk_tags WHERE client_org_id = ?"
        params: list[Any] = [client_org_id]
        if risk_id:
            sql += " AND risk_id = ?"
            params.append(risk_id)
        if status:
            sql += " AND tag_status = ?"
            params.append(status)
        sql += " ORDER BY datetime(created_at) DESC LIMIT ?"
        params.append(limit)
        cur = await self._conn.execute(sql, tuple(params))
        rows = await cur.fetchall()
        return [_row_to_risk_tag(dict(r)) for r in rows]

    async def latest_for_risk(self, risk_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            "SELECT * FROM risk_tags WHERE risk_id = ? ORDER BY datetime(created_at) DESC LIMIT 1",
            (risk_id,),
        )
        row = await cur.fetchone()
        return _row_to_risk_tag(dict(row)) if row else None

    async def delete_open_for_risk(self, risk_id: str, run_job_id: Optional[str] = None) -> None:
        await self._conn.execute(
            "DELETE FROM risk_tags WHERE risk_id = ? AND tag_status IN ('proposed', 'needs_review')",
            (risk_id,),
        )
        await self._conn.commit()

    async def update_review(
        self,
        row_id: str,
        *,
        tag_status: str,
        reviewer_user_id: Optional[str],
        reviewer_notes: Optional[str],
    ) -> None:
        await self._conn.execute(
            """
            UPDATE risk_tags
            SET tag_status = ?, reviewer_user_id = ?, reviewer_notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (tag_status, reviewer_user_id, reviewer_notes, _now_iso(), row_id),
        )
        await self._conn.commit()

    async def count_distinct_risks_by_status(self, client_org_id: str, status: str) -> int:
        cur = await self._conn.execute(
            "SELECT COUNT(DISTINCT risk_id) FROM risk_tags WHERE client_org_id = ? AND tag_status = ?",
            (client_org_id, status),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def last_updated_at(self, client_org_id: str) -> Optional[str]:
        cur = await self._conn.execute(
            "SELECT MAX(updated_at) FROM risk_tags WHERE client_org_id = ?",
            (client_org_id,),
        )
        row = await cur.fetchone()
        return str(row[0]) if row and row[0] else None
