from __future__ import annotations

from typing import Annotated

import aiosqlite
from fastapi import Depends

from iso_robot.config import Settings, get_settings
from iso_robot.repositories.db import get_db
from iso_robot.repositories.control_repository import ControlRepository
from iso_robot.repositories.document_repository import DocumentRepository
from iso_robot.repositories.job_repository import JobRepository
from iso_robot.repositories.org_repository import (
    AuditLogRepository,
    ControlDocumentRepository,
    DemographyRepository,
    FolderRepository,
    IssueScoreRepository,
    OrgRepository,
    RiskRepository,
    TenantRepository,
    UserRepository,
)


# ── Existing dependencies (DO NOT CHANGE) ────────────────────────────────────

async def get_document_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> DocumentRepository:
    return DocumentRepository(db)


async def get_job_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> JobRepository:
    return JobRepository(db)


async def get_control_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> ControlRepository:
    return ControlRepository(db)


def get_app_settings() -> Settings:
    return get_settings()


# ── New dependencies ──────────────────────────────────────────────────────────

async def get_org_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> OrgRepository:
    return OrgRepository(db)


async def get_user_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> UserRepository:
    return UserRepository(db)


async def get_tenant_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> TenantRepository:
    return TenantRepository(db)


async def get_folder_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> FolderRepository:
    return FolderRepository(db)


async def get_demography_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> DemographyRepository:
    return DemographyRepository(db)


async def get_control_document_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> ControlDocumentRepository:
    return ControlDocumentRepository(db)


async def get_issue_score_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> IssueScoreRepository:
    return IssueScoreRepository(db)


async def get_risk_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> RiskRepository:
    return RiskRepository(db)


async def get_audit_repo(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> AuditLogRepository:
    return AuditLogRepository(db)

# ─────────────────────────────────────────────────────────────────────────────
# Auth dependency — reads the claims the middleware already validated, loads user.
# ─────────────────────────────────────────────────────────────────────────────
from fastapi import Request  # noqa: E402

from iso_robot.errors import APIError  # noqa: E402
from iso_robot.repositories.org_repository import UserRepository  # noqa: E402


async def get_user_repo_for_auth(
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> UserRepository:
    return UserRepository(db)


async def get_current_user(
    request: Request,
    user_repo: Annotated[UserRepository, Depends(get_user_repo_for_auth)],
) -> dict:
    claims = getattr(request.state, "user_claims", None)
    if not claims or "sub" not in claims:
        raise APIError("Not authenticated", code="UNAUTHORIZED", status_code=401)
    user = await user_repo.get_by_id(claims["sub"])
    if not user or not user.get("is_active", 1):
        raise APIError("User not found or inactive", code="UNAUTHORIZED", status_code=401)
    return user

async def require_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    if current_user.get("role") != "admin":
        raise APIError("Admin privileges required", code="FORBIDDEN", status_code=403)
    return current_user