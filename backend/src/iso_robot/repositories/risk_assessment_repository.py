"""Persistence for risk assessments. Mirrors ``IssueClassificationRepository``:
the full assessment dict is stored as JSON, keyed by issue, newest-wins.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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


class RiskAssessmentRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def delete_for_issue(self, issue_id: str) -> None:
        await self._conn.execute("DELETE FROM risk_assessments WHERE issue_id = ?", (issue_id,))
        await self._conn.commit()

    async def insert(
        self,
        *,
        row_id: str,
        issue_id: str,
        assessment: Dict[str, Any],
        model_version: Optional[str] = None,
    ) -> None:
        # Flatten the headline fields into columns for easy querying/dashboarding;
        # keep the full structure (incl. per-control detail) in assessment_json.
        await self._conn.execute(
            """
            INSERT INTO risk_assessments (
                id, issue_id, risk_type, likelihood, consequence, velocity,
                inherent_risk, overall_control_effectiveness, residual_risk,
                risk_response, assessment_json, model_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                issue_id,
                assessment.get("risk_type"),
                assessment.get("likelihood"),
                assessment.get("consequence"),
                assessment.get("velocity"),
                assessment.get("inherent_risk"),
                assessment.get("overall_control_effectiveness"),
                assessment.get("residual_risk"),
                assessment.get("risk_response"),
                dumps_json(assessment),
                model_version,
                _now_iso(),
            ),
        )
        await self._conn.commit()

    async def get_latest_for_issue(self, issue_id: str) -> Optional[Dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT id, issue_id, assessment_json, model_version, created_at
            FROM risk_assessments WHERE issue_id = ?
            ORDER BY datetime(created_at) DESC LIMIT 1
            """,
            (issue_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["assessment"] = _loads_json(d.pop("assessment_json", None))
        return d

    async def list_all(self, limit: int = 2000, offset: int = 0) -> List[Dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT id, issue_id, assessment_json, model_version, created_at
            FROM risk_assessments
            ORDER BY datetime(created_at) DESC LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        rows = await cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["assessment"] = _loads_json(d.pop("assessment_json", None))
            out.append(d)
        return out
