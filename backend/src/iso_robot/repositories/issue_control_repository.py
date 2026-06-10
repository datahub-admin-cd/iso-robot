"""Stores and reads the link between issues and the controls assigned to them.

This is the 'mapping table' layer. One row in `issue_controls` means
'this control belongs to this issue'. Scoring uses it to fetch exactly the
controls for the issue being scored, instead of the whole register.
"""

from __future__ import annotations

from typing import List

import aiosqlite


class IssueControlRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def assign(self, issue_id: str, control_ids: List[str]) -> int:
        """Link a list of control ids to one issue. Ignores duplicates."""
        count = 0
        for cid in control_ids:
            cid = str(cid).strip()
            if not cid:
                continue
            await self._conn.execute(
                "INSERT OR IGNORE INTO issue_controls (issue_id, control_id) VALUES (?, ?)",
                (issue_id, cid),
            )
            count += 1
        await self._conn.commit()
        return count

    async def clear(self, issue_id: str) -> None:
        """Remove all control links for an issue (used before re-assigning)."""
        await self._conn.execute("DELETE FROM issue_controls WHERE issue_id = ?", (issue_id,))
        await self._conn.commit()

    async def list_control_texts_for_issue(self, issue_id: str) -> List[str]:
        """Return the control_text of every control assigned to this issue."""
        cur = await self._conn.execute(
            """
            SELECT c.control_text
            FROM issue_controls ic
            JOIN controls c ON c.id = ic.control_id
            WHERE ic.issue_id = ?
            ORDER BY c.section_ref
            """,
            (issue_id,),
        )
        rows = await cur.fetchall()
        return [str(r["control_text"]).strip() for r in rows if r["control_text"]]
