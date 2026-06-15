from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from iso_robot.repositories.db import dumps_json


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _loads_json(raw: Any) -> Any:
    if raw is None or raw == "":
        return []
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Client Organizations
# ─────────────────────────────────────────────────────────────────────────────

class OrgRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(
        self,
        *,
        name: str,
        slug: str,
        industry: Optional[str] = None,
        region: Optional[str] = None,
    ) -> dict[str, Any]:
        org_id = str(uuid.uuid4())
        await self._conn.execute(
            """
            INSERT INTO client_organizations (id, name, slug, industry, region, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (org_id, name, slug, industry, region, _now_iso()),
        )
        await self._conn.commit()
        row = await self.get_by_id(org_id)
        return row  # type: ignore[return-value]

    async def get_by_id(self, org_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            "SELECT id, name, slug, industry, region, created_at FROM client_organizations WHERE id = ?",
            (org_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def get_by_slug(self, slug: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            "SELECT id, name, slug, industry, region, created_at FROM client_organizations WHERE slug = ?",
            (slug,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def list_all(self) -> List[dict[str, Any]]:
        cur = await self._conn.execute(
            "SELECT id, name, slug, industry, region, created_at FROM client_organizations ORDER BY name"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────────────

class UserRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: Optional[str],
        client_org_id: str,
        role: str = "analyst",
    ) -> dict[str, Any]:
        user_id = str(uuid.uuid4())
        await self._conn.execute(
            """
            INSERT INTO users (id, email, hashed_password, full_name, client_org_id, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (user_id, email, hashed_password, full_name, client_org_id, role, _now_iso()),
        )
        await self._conn.commit()
        return await self.get_by_email(email)  # type: ignore[return-value]

    async def get_by_email(self, email: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT id, email, hashed_password, full_name, client_org_id, role, is_active, created_at
            FROM users WHERE email = ?
            """,
            (email,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def get_by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT id, email, hashed_password, full_name, client_org_id, role, is_active, created_at
            FROM users WHERE id = ?
            """,
            (user_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Tenant Mapping
# ─────────────────────────────────────────────────────────────────────────────

class TenantRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(self, *, client_org_id: str, tenant_id: str) -> dict[str, Any]:
        row_id = str(uuid.uuid4())
        await self._conn.execute(
            """
            INSERT INTO tenant_mapping (id, client_org_id, tenant_id, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tenant_id) DO NOTHING
            """,
            (row_id, client_org_id, tenant_id, _now_iso()),
        )
        await self._conn.commit()
        return await self.get_by_org(client_org_id)  # type: ignore[return-value]

    async def get_by_org(self, client_org_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            "SELECT id, client_org_id, tenant_id, created_at FROM tenant_mapping WHERE client_org_id = ?",
            (client_org_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Folder Mapping
# ─────────────────────────────────────────────────────────────────────────────

class FolderRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def set_folder_path(
        self,
        *,
        client_org_id: str,
        folder_type: str,
        folder_path: str,
    ) -> None:
        cur = await self._conn.execute(
            """
            SELECT id FROM folder_mapping
            WHERE client_org_id = ? AND folder_type = ?
            """,
            (client_org_id, folder_type),
        )
        row = await cur.fetchone()
        if row:
            await self._conn.execute(
                """
                UPDATE folder_mapping SET folder_path = ?
                WHERE client_org_id = ? AND folder_type = ?
                """,
                (folder_path, client_org_id, folder_type),
            )
        else:
            await self._conn.execute(
                """
                INSERT INTO folder_mapping (id, client_org_id, folder_type, folder_path, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), client_org_id, folder_type, folder_path, _now_iso()),
            )
        await self._conn.commit()

    async def upsert(self, *, client_org_id: str, folder_type: str, folder_path: str) -> None:
        await self.set_folder_path(
            client_org_id=client_org_id,
            folder_type=folder_type,
            folder_path=folder_path,
        )

    async def get_folders_for_org(self, client_org_id: str) -> Dict[str, str]:
        """Returns a dict like {'control_documents': '/path/...', 'issues': '/path/...'}"""
        cur = await self._conn.execute(
            "SELECT folder_type, folder_path FROM folder_mapping WHERE client_org_id = ?",
            (client_org_id,),
        )
        rows = await cur.fetchall()
        return {str(r[0]): str(r[1]) for r in rows}

    async def insert_bulk(self, client_org_id: str, folders: Dict[str, str]) -> None:
        """Insert multiple folder types at once during org onboarding."""
        for folder_type, folder_path in folders.items():
            row_id = str(uuid.uuid4())
            await self._conn.execute(
                """
                INSERT INTO folder_mapping (id, client_org_id, folder_type, folder_path, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (row_id, client_org_id, folder_type, folder_path, _now_iso()),
            )
        await self._conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Business Demography
# ─────────────────────────────────────────────────────────────────────────────

class DemographyRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def upsert(
        self,
        *,
        client_org_id: str,
        industry: Optional[str] = None,
        sub_industry: Optional[str] = None,
        employee_count: Optional[str] = None,
        annual_revenue: Optional[str] = None,
        headquarters_country: Optional[str] = None,
        headquarters_city: Optional[str] = None,
        ownership_type: Optional[str] = None,
        regulatory_region: Optional[str] = None,
        website: Optional[str] = None,
        functions: Optional[List[str]] = None,
        locations: Optional[List[dict]] = None,
        processes: Optional[List[dict]] = None,
        regulatory_frameworks: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        now = _now_iso()
        row_id = str(uuid.uuid4())
        await self._conn.execute(
            """
            INSERT INTO business_demography (
              id, client_org_id, industry, sub_industry, employee_count, annual_revenue,
              headquarters_country, headquarters_city, ownership_type, regulatory_region,
              website, functions_json, locations_json, processes_json,
              regulatory_frameworks_json, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_org_id) DO UPDATE SET
              industry = COALESCE(excluded.industry, industry),
              sub_industry = COALESCE(excluded.sub_industry, sub_industry),
              employee_count = COALESCE(excluded.employee_count, employee_count),
              annual_revenue = COALESCE(excluded.annual_revenue, annual_revenue),
              headquarters_country = COALESCE(excluded.headquarters_country, headquarters_country),
              headquarters_city = COALESCE(excluded.headquarters_city, headquarters_city),
              ownership_type = COALESCE(excluded.ownership_type, ownership_type),
              regulatory_region = COALESCE(excluded.regulatory_region, regulatory_region),
              website = COALESCE(excluded.website, website),
              functions_json = COALESCE(excluded.functions_json, functions_json),
              locations_json = COALESCE(excluded.locations_json, locations_json),
              processes_json = COALESCE(excluded.processes_json, processes_json),
              regulatory_frameworks_json = COALESCE(excluded.regulatory_frameworks_json, regulatory_frameworks_json),
              notes = COALESCE(excluded.notes, notes),
              updated_at = excluded.updated_at
            """,
            (
                row_id, client_org_id, industry, sub_industry, employee_count, annual_revenue,
                headquarters_country, headquarters_city, ownership_type, regulatory_region,
                website,
                dumps_json(functions or []),
                dumps_json(locations or []),
                dumps_json(processes or []),
                dumps_json(regulatory_frameworks or []),
                notes, now, now,
            ),
        )
        await self._conn.commit()
        return await self.get_by_org(client_org_id)  # type: ignore[return-value]

    async def get_by_org(self, client_org_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT id, client_org_id, industry, sub_industry, employee_count, annual_revenue,
                   headquarters_country, headquarters_city, ownership_type, regulatory_region,
                   website, functions_json, locations_json, processes_json,
                   regulatory_frameworks_json, notes, created_at, updated_at
            FROM business_demography WHERE client_org_id = ?
            """,
            (client_org_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["functions"] = _loads_json(d.pop("functions_json", "[]"))
        d["locations"] = _loads_json(d.pop("locations_json", "[]"))
        d["processes"] = _loads_json(d.pop("processes_json", "[]"))
        d["regulatory_frameworks"] = _loads_json(d.pop("regulatory_frameworks_json", "[]"))
        return d


# ─────────────────────────────────────────────────────────────────────────────
# Control Documents (per-org uploaded documents)
# ─────────────────────────────────────────────────────────────────────────────

class ControlDocumentRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(
        self,
        *,
        client_org_id: str,
        filename: str,
        document_path: str,
        document_type: Optional[str] = None,
        document_category: Optional[str] = None,
        document_version: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> dict[str, Any]:
        doc_id = str(uuid.uuid4())
        await self._conn.execute(
            """
            INSERT INTO control_documents (
              id, client_org_id, filename, document_path, document_type,
              document_category, document_version, uploaded_by,
              processing_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ready_for_extraction', ?)
            """,
            (
                doc_id, client_org_id, filename, document_path,
                document_type, document_category, document_version,
                uploaded_by, _now_iso(),
            ),
        )
        await self._conn.commit()
        return await self.get_by_id(doc_id)  # type: ignore[return-value]

    async def get_by_id(self, doc_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT id, client_org_id, filename, document_path, document_type,
                   document_category, document_version, uploaded_by,
                   processing_status, created_at
            FROM control_documents WHERE id = ?
            """,
            (doc_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def list_for_org(self, client_org_id: str) -> List[dict[str, Any]]:
        cur = await self._conn.execute(
            """
            SELECT id, client_org_id, filename, document_path, document_type,
                   document_category, document_version, uploaded_by,
                   processing_status, created_at
            FROM control_documents WHERE client_org_id = ?
            ORDER BY datetime(created_at) DESC
            """,
            (client_org_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def update_status(self, doc_id: str, status: str) -> None:
        await self._conn.execute(
            "UPDATE control_documents SET processing_status = ? WHERE id = ?",
            (status, doc_id),
        )
        await self._conn.commit()

    async def update_document_path(self, doc_id: str, document_path: str) -> None:
        await self._conn.execute(
            "UPDATE control_documents SET document_path = ? WHERE id = ?",
            (document_path, doc_id),
        )
        await self._conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Issue Scores
# ─────────────────────────────────────────────────────────────────────────────

class IssueScoreRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def upsert(
        self,
        *,
        issue_id: str,
        client_org_id: str,
        risk_score: Optional[int] = None,
        risk_rating: Optional[str] = None,
        likelihood_score: Optional[int] = None,
        impact_score: Optional[int] = None,
        velocity_score: Optional[int] = None,
        mapped_functions: Optional[List[str]] = None,
        mapped_locations: Optional[List[str]] = None,
        mapped_processes: Optional[List[str]] = None,
        recommended_risk_title: Optional[str] = None,
        scoring_run_id: Optional[str] = None,
    ) -> dict[str, Any]:
        row_id = str(uuid.uuid4())
        now = _now_iso()
        await self._conn.execute(
            """
            INSERT INTO issue_scores (
              id, issue_id, client_org_id, risk_score, risk_rating,
              likelihood_score, impact_score, velocity_score,
              mapped_functions_json, mapped_locations_json, mapped_processes_json,
              recommended_risk_title, scoring_run_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              risk_score = excluded.risk_score,
              risk_rating = excluded.risk_rating,
              likelihood_score = excluded.likelihood_score,
              impact_score = excluded.impact_score,
              velocity_score = excluded.velocity_score,
              mapped_functions_json = excluded.mapped_functions_json,
              mapped_locations_json = excluded.mapped_locations_json,
              mapped_processes_json = excluded.mapped_processes_json,
              recommended_risk_title = excluded.recommended_risk_title
            """,
            (
                row_id, issue_id, client_org_id, risk_score, risk_rating,
                likelihood_score, impact_score, velocity_score,
                dumps_json(mapped_functions or []),
                dumps_json(mapped_locations or []),
                dumps_json(mapped_processes or []),
                recommended_risk_title, scoring_run_id, now,
            ),
        )
        await self._conn.commit()
        cur = await self._conn.execute(
            "SELECT * FROM issue_scores WHERE issue_id = ? ORDER BY datetime(created_at) DESC LIMIT 1",
            (issue_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else {}

    async def list_for_org(self, client_org_id: str) -> List[dict[str, Any]]:
        cur = await self._conn.execute(
            "SELECT * FROM issue_scores WHERE client_org_id = ? ORDER BY risk_score DESC",
            (client_org_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Risks (final approved risks)
# ─────────────────────────────────────────────────────────────────────────────

class RiskRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(
        self,
        *,
        client_org_id: str,
        issue_id: Optional[str],
        risk_title: str,
        risk_description: Optional[str],
        risk_rating: Optional[str],
        risk_score: Optional[int],
        mapped_controls: Optional[List[str]] = None,
        mapped_functions: Optional[List[str]] = None,
        mapped_locations: Optional[List[str]] = None,
        mapped_processes: Optional[List[str]] = None,
        submitted_by: Optional[str] = None,
    ) -> dict[str, Any]:
        risk_id = str(uuid.uuid4())
        await self._conn.execute(
            """
            INSERT INTO risks (
              id, client_org_id, issue_id, risk_title, risk_description,
              risk_rating, risk_score, mapped_controls_json,
              mapped_functions_json, mapped_locations_json, mapped_processes_json,
              submitted_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                risk_id, client_org_id, issue_id, risk_title, risk_description,
                risk_rating, risk_score,
                dumps_json(mapped_controls or []),
                dumps_json(mapped_functions or []),
                dumps_json(mapped_locations or []),
                dumps_json(mapped_processes or []),
                submitted_by, _now_iso(),
            ),
        )
        await self._conn.commit()
        cur = await self._conn.execute("SELECT * FROM risks WHERE id = ?", (risk_id,))
        row = await cur.fetchone()
        return dict(row) if row else {}

    async def list_for_org(self, client_org_id: str, limit: int = 1000) -> List[dict[str, Any]]:
        cur = await self._conn.execute(
            "SELECT * FROM risks WHERE client_org_id = ? ORDER BY datetime(created_at) DESC LIMIT ?",
            (client_org_id, limit),
        )
        rows = await cur.fetchall()
        return [self._normalize(dict(r)) for r in rows]

    async def get_by_id(self, risk_id: str) -> Optional[dict[str, Any]]:
        cur = await self._conn.execute("SELECT * FROM risks WHERE id = ?", (risk_id,))
        row = await cur.fetchone()
        return self._normalize(dict(row)) if row else None

    async def count_for_org(self, client_org_id: str) -> int:
        cur = await self._conn.execute(
            "SELECT COUNT(*) FROM risks WHERE client_org_id = ?",
            (client_org_id,),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def update_applied_tags(
        self,
        risk_id: str,
        *,
        tags_by_dimension: Dict[str, List[dict[str, Any]]],
        tag_status: str,
    ) -> None:
        await self._conn.execute(
            """
            UPDATE risks SET
              process_tags_json = ?,
              function_tags_json = ?,
              department_tags_json = ?,
              kpi_tags_json = ?,
              region_tags_json = ?,
              control_family_tags_json = ?,
              tag_status = ?,
              updated_at = ?
            WHERE id = ?
            """,
            (
                dumps_json(tags_by_dimension.get("process") or []),
                dumps_json(tags_by_dimension.get("function") or []),
                dumps_json(tags_by_dimension.get("department") or []),
                dumps_json(tags_by_dimension.get("kpi") or []),
                dumps_json(tags_by_dimension.get("region") or []),
                dumps_json(tags_by_dimension.get("control_family") or []),
                tag_status, _now_iso(), risk_id,
            ),
        )
        await self._conn.commit()

    async def update_owner(
        self,
        risk_id: str,
        *,
        owner_user_id: Optional[str],
        accountable_user_id: Optional[str],
        owner_assignment_status: str,
    ) -> None:
        await self._conn.execute(
            """
            UPDATE risks SET
              owner_user_id = ?,
              accountable_user_id = ?,
              owner_assignment_status = ?,
              updated_at = ?
            WHERE id = ?
            """,
            (owner_user_id, accountable_user_id, owner_assignment_status, _now_iso(), risk_id),
        )
        await self._conn.commit()

    @staticmethod
    def _normalize(row: dict[str, Any]) -> dict[str, Any]:
        for key in (
            "mapped_controls", "mapped_functions", "mapped_locations", "mapped_processes",
            "process_tags", "function_tags", "department_tags",
            "kpi_tags", "region_tags", "control_family_tags",
        ):
            raw = row.pop(f"{key}_json", None)
            row[key] = _loads_json(raw)
        row.setdefault("tag_status", "untagged")
        row.setdefault("owner_assignment_status", "unassigned")
        return row


# ─────────────────────────────────────────────────────────────────────────────
# Audit Log
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def log(
        self,
        *,
        api_name: str,
        client_org_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        requested_by: Optional[str] = None,
        status: str = "success",
        input_metadata: Optional[dict] = None,
        output_metadata: Optional[dict] = None,
        error_details: Optional[str] = None,
    ) -> str:
        log_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        now = _now_iso()
        await self._conn.execute(
            """
            INSERT INTO api_audit_log (
              id, request_id, api_name, client_org_id, tenant_id, requested_by,
              request_timestamp, completion_timestamp, status,
              input_metadata_json, output_metadata_json, error_details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id, request_id, api_name, client_org_id, tenant_id, requested_by,
                now, now, status,
                dumps_json(input_metadata or {}),
                dumps_json(output_metadata or {}),
                error_details,
            ),
        )
        await self._conn.commit()
        return request_id