from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from iso_robot.repositories.db import dumps_json

ASSIGNMENT_STATUSES = ("proposed", "assigned", "needs_review", "rejected")
ASSIGNMENT_TYPES = ("primary_owner", "accountable_owner", "delegate", "alternate_owner")


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


def _row_to_hierarchy_user(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["ownership_roles"] = _loads_json(out.pop("ownership_roles_json", "[]"), [])
    out["owned_process_ids"] = _loads_json(out.pop("owned_process_ids_json", "[]"), [])
    out["owned_kpi_ids"] = _loads_json(out.pop("owned_kpi_ids_json", "[]"), [])
    out["is_active"] = bool(out.get("is_active", 1))
    return out


def _row_to_assignment(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["recommended_owner"] = _loads_json(out.pop("recommended_owner_json", "{}"), {})
    out["alternate_owners"] = _loads_json(out.pop("alternate_owners_json", "[]"), [])
    out["matched_on"] = _loads_json(out.pop("matched_on_json", "[]"), [])
    out["inputs"] = _loads_json(out.pop("inputs_json", "{}"), {})
    return out


class OrgHierarchyRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create_snapshot(
        self,
        *,
        client_org_id: str,
        snapshot_status: str = "approved",
        source: Optional[str] = None,
    ) -> dict[str, Any]:
        snapshot_id = str(uuid.uuid4())
        await self._conn.execute(
            """
            INSERT INTO org_hierarchy_snapshots (id, client_org_id, snapshot_status, source, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (snapshot_id, client_org_id, snapshot_status, source, _now_iso()),
        )
        await self._conn.commit()
        return (await self.get_snapshot(snapshot_id))  # type: ignore[return-value]

    async def get_snapshot(self, snapshot_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            "SELECT * FROM org_hierarchy_snapshots WHERE id = ?",
            (snapshot_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def latest_approved(self, client_org_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT * FROM org_hierarchy_snapshots
            WHERE client_org_id = ? AND snapshot_status = 'approved'
            ORDER BY datetime(created_at) DESC LIMIT 1
            """,
            (client_org_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def insert_users(self, snapshot_id: str, users: List[dict[str, Any]]) -> int:
        now = _now_iso()
        for u in users:
            await self._conn.execute(
                """
                INSERT INTO org_hierarchy_users (
                  id, snapshot_id, client_org_id, user_id, name, email, title,
                  function, department, region, management_level, manager_user_id,
                  is_active, ownership_roles_json, owned_process_ids_json,
                  owned_kpi_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    snapshot_id,
                    u["client_org_id"],
                    u["user_id"],
                    u.get("name"),
                    u.get("email"),
                    u.get("title"),
                    u.get("function"),
                    u.get("department"),
                    u.get("region"),
                    u.get("management_level"),
                    u.get("manager_user_id"),
                    1 if u.get("is_active", True) else 0,
                    dumps_json(u.get("ownership_roles") or []),
                    dumps_json(u.get("owned_process_ids") or []),
                    dumps_json(u.get("owned_kpi_ids") or []),
                    now,
                ),
            )
        await self._conn.commit()
        return len(users)

    async def list_users(
        self,
        snapshot_id: str,
        *,
        include_inactive: bool = False,
    ) -> List[dict[str, Any]]:
        sql = "SELECT * FROM org_hierarchy_users WHERE snapshot_id = ?"
        if not include_inactive:
            sql += " AND is_active = 1"
        sql += " ORDER BY name"
        cur = await self._conn.execute(sql, (snapshot_id,))
        rows = await cur.fetchall()
        return [_row_to_hierarchy_user(dict(r)) for r in rows]

    async def get_user(self, snapshot_id: str, user_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            "SELECT * FROM org_hierarchy_users WHERE snapshot_id = ? AND user_id = ?",
            (snapshot_id, user_id),
        )
        row = await cur.fetchone()
        return _row_to_hierarchy_user(dict(row)) if row else None

    async def get_user_any_snapshot(self, client_org_id: str, user_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT * FROM org_hierarchy_users
            WHERE client_org_id = ? AND user_id = ?
            ORDER BY datetime(created_at) DESC LIMIT 1
            """,
            (client_org_id, user_id),
        )
        row = await cur.fetchone()
        return _row_to_hierarchy_user(dict(row)) if row else None


class RiskAssignmentRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def insert(
        self,
        *,
        client_org_id: str,
        risk_id: str,
        recommended_owner_user_id: Optional[str],
        recommended_owner: Optional[dict[str, Any]],
        alternate_owners: Optional[List[dict[str, Any]]],
        assignment_status: str,
        confidence: Optional[float],
        matched_on: Optional[List[str]],
        rationale: Optional[str],
        inputs: Optional[dict[str, Any]] = None,
        hierarchy_snapshot_id: Optional[str] = None,
        run_job_id: Optional[str] = None,
        auto_applied: bool = False,
    ) -> dict[str, Any]:
        row_id = str(uuid.uuid4())
        now = _now_iso()
        await self._conn.execute(
            """
            INSERT INTO risk_assignments (
              id, client_org_id, risk_id, recommended_owner_user_id,
              recommended_owner_json, alternate_owners_json, assignment_status,
              confidence, matched_on_json, rationale, inputs_json,
              hierarchy_snapshot_id, run_job_id, auto_applied, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id, client_org_id, risk_id, recommended_owner_user_id,
                dumps_json(recommended_owner or {}),
                dumps_json(alternate_owners or []),
                assignment_status, confidence,
                dumps_json(matched_on or []),
                rationale,
                dumps_json(inputs or {}),
                hierarchy_snapshot_id, run_job_id, 1 if auto_applied else 0,
                now, now,
            ),
        )
        await self._conn.commit()
        return (await self.get_by_id(row_id))  # type: ignore[return-value]

    async def get_by_id(self, row_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute("SELECT * FROM risk_assignments WHERE id = ?", (row_id,))
        row = await cur.fetchone()
        return _row_to_assignment(dict(row)) if row else None

    async def list_for_org(
        self,
        client_org_id: str,
        *,
        risk_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict[str, Any]]:
        sql = "SELECT * FROM risk_assignments WHERE client_org_id = ?"
        params: list[Any] = [client_org_id]
        if risk_id:
            sql += " AND risk_id = ?"
            params.append(risk_id)
        if status:
            sql += " AND assignment_status = ?"
            params.append(status)
        sql += " ORDER BY datetime(created_at) DESC LIMIT ?"
        params.append(limit)
        cur = await self._conn.execute(sql, tuple(params))
        rows = await cur.fetchall()
        return [_row_to_assignment(dict(r)) for r in rows]

    async def latest_for_risk(self, risk_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            "SELECT * FROM risk_assignments WHERE risk_id = ? ORDER BY datetime(created_at) DESC LIMIT 1",
            (risk_id,),
        )
        row = await cur.fetchone()
        return _row_to_assignment(dict(row)) if row else None

    async def delete_open_for_risk(self, risk_id: str) -> None:
        await self._conn.execute(
            "DELETE FROM risk_assignments WHERE risk_id = ? AND assignment_status IN ('proposed', 'needs_review')",
            (risk_id,),
        )
        await self._conn.commit()

    async def update_review(
        self,
        row_id: str,
        *,
        assignment_status: str,
        accountable_user_id: Optional[str] = None,
        assignment_type: Optional[str] = None,
        reviewer_user_id: Optional[str] = None,
        reviewer_notes: Optional[str] = None,
    ) -> None:
        await self._conn.execute(
            """
            UPDATE risk_assignments
            SET assignment_status = ?,
                accountable_user_id = COALESCE(?, accountable_user_id),
                assignment_type = COALESCE(?, assignment_type),
                reviewer_user_id = ?, reviewer_notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                assignment_status, accountable_user_id, assignment_type,
                reviewer_user_id, reviewer_notes, _now_iso(), row_id,
            ),
        )
        await self._conn.commit()

    async def count_distinct_risks_by_status(self, client_org_id: str, status: str) -> int:
        cur = await self._conn.execute(
            "SELECT COUNT(DISTINCT risk_id) FROM risk_assignments WHERE client_org_id = ? AND assignment_status = ?",
            (client_org_id, status),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def last_updated_at(self, client_org_id: str) -> Optional[str]:
        cur = await self._conn.execute(
            "SELECT MAX(updated_at) FROM risk_assignments WHERE client_org_id = ?",
            (client_org_id,),
        )
        row = await cur.fetchone()
        return str(row[0]) if row and row[0] else None
