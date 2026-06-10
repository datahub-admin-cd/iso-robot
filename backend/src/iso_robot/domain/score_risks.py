"""Risk-scoring orchestration. Mirrors ``domain/classify_issues.py``:
a per-issue function and a batch job function, both async, both using the
existing ``chat_json_object`` LLM helper and the repository layer.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

import aiosqlite

from iso_robot.config import Settings
from iso_robot.domain import risk_scoring as rs
from iso_robot.domain.llm_service import chat_json_object
from iso_robot.repositories.issue_repository import IssueRepository
from iso_robot.repositories.risk_assessment_repository import RiskAssessmentRepository
from iso_robot.repositories.issue_control_repository import IssueControlRepository

logger = logging.getLogger(__name__)


def _issue_text(row: Dict[str, Any]) -> str:
    title = (row.get("title") or "").strip()
    body = (row.get("body") or "").strip()
    return f"{title}\n\n{body}".strip() if title or body else ""


async def _resolve_controls(
    conn: aiosqlite.Connection,
    issue_id: str,
    payload_controls: Optional[List[str]],
) -> List[str]:
    if payload_controls:
        return [c for c in (s.strip() for s in payload_controls) if c]
    return await IssueControlRepository(conn).list_control_texts_for_issue(issue_id)


async def score_issue(
    settings: Settings,
    conn: aiosqlite.Connection,
    issue_id: str,
    controls: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Run the full 10-step assessment for one issue and persist it."""
    issues = IssueRepository(conn)
    repo = RiskAssessmentRepository(conn)

    row = await issues.get_by_id(issue_id)
    if row is None:
        return None

    issue_text = _issue_text(row)
    control_texts = await _resolve_controls(conn, issue_id, controls)
    model_version = settings.azure_openai_deployment or None

    data = await chat_json_object(
        settings,
        system=rs.SYSTEM_PROMPT,
        user=rs.build_user_prompt(issue_text, control_texts),
        
    )
    judgment = rs.normalize_llm_output(data)   # raises on out-of-vocabulary values
    assessment = rs.score_from_judgment(judgment)

    await repo.delete_for_issue(issue_id)
    await repo.insert(
        row_id=str(uuid.uuid4()),
        issue_id=issue_id,
        assessment=assessment,
        model_version=model_version,
    )
    return assessment


async def score_risks_job(
    settings: Settings,
    conn: aiosqlite.Connection,
    issue_ids: Optional[List[str]],
    controls: Optional[List[str]] = None,
    *,
    client_org_id: Optional[str] = None,
) -> int:
    """Batch entry point invoked by the job runner."""
    issues = IssueRepository(conn)
    if issue_ids:
        todo = [i for i in issue_ids if i]
    else:
        rows = await issues.list_all(limit=2000, offset=0, client_org_id=client_org_id)
        todo = [r["id"] for r in rows]

    done = 0
    for iid in todo:
        try:
            if await score_issue(settings, conn, str(iid), controls) is not None:
                done += 1
        except Exception as exc:  # one bad issue must not kill the batch
            logger.warning("Risk scoring failed for %s: %s", iid, exc)
    return done
