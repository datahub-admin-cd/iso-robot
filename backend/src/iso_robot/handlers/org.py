from __future__ import annotations

from pathlib import Path
from typing import Annotated, List, Optional

from fastapi import Depends, File, Form, UploadFile

from iso_robot.config import Settings
from iso_robot.deps import (
    get_app_settings,
    get_audit_repo,
    get_control_document_repo,
    get_demography_repo,
    get_folder_repo,
    get_issue_score_repo,
    get_org_repo,
    get_risk_repo,
    get_tenant_repo,
    get_user_repo,
    require_admin,
)
from iso_robot.errors import APIError
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
from iso_robot.domain.repair_storage_paths import sync_org_folder_mapping
from iso_robot.helpers.org_paths import resolve_file_in_folder
from iso_robot.schemas.api import (
    ApiResponse,
    ControlDocumentResponse,
    DemographyResponse,
    DemographyUpdateRequest,
    OrgCreateRequest,
    OrgResponse,
    RiskUploadRequest,
)


# ── API: Create Organisation ──────────────────────────────────────────────────

async def create_org(
    body: OrgCreateRequest,
    org_repo: Annotated[OrgRepository, Depends(get_org_repo)],
    folder_repo: Annotated[FolderRepository, Depends(get_folder_repo)],
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repo)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    _admin: Annotated[dict, Depends(require_admin)],
) -> ApiResponse:
    """Create a new client organisation with auto-created folders and tenant mapping."""
    existing = await org_repo.get_by_slug(body.slug)
    if existing:
        raise APIError("Slug already taken", code="DUPLICATE_RECORD", status_code=409)

    org = await org_repo.create(
        name=body.name,
        slug=body.slug,
        industry=body.industry,
        region=body.region,
    )
    org_id = org["id"]

    folder_types = await sync_org_folder_mapping(
        settings,
        folder_repo,
        client_org_id=org_id,
        org_slug=org["slug"],
    )

    # Create tenant mapping (tenant_id = slug for simplicity)
    await tenant_repo.create(client_org_id=org_id, tenant_id=body.slug)

    return ApiResponse(
        status="success",
        message="Organisation created successfully",
        data=OrgResponse(**org).model_dump(),
    )


async def list_orgs(
    org_repo: Annotated[OrgRepository, Depends(get_org_repo)],
) -> ApiResponse:
    orgs = await org_repo.list_all()
    return ApiResponse(
        status="success",
        message="Organisations retrieved",
        data={"organisations": [OrgResponse(**o).model_dump() for o in orgs]},
    )


# ── API 3: Business Demography Update ─────────────────────────────────────────

async def update_demography(
    body: DemographyUpdateRequest,
    org_repo: Annotated[OrgRepository, Depends(get_org_repo)],
    demo_repo: Annotated[DemographyRepository, Depends(get_demography_repo)],
    audit_repo: Annotated[AuditLogRepository, Depends(get_audit_repo)],
) -> ApiResponse:
    """API 3: Update business demography for a client organisation."""
    org = await org_repo.get_by_id(body.client_org_id)
    if not org:
        raise APIError("Organisation not found", code="CLIENT_ORG_NOT_FOUND", status_code=404)

    bd = body.business_demography
    demo = await demo_repo.upsert(
        client_org_id=body.client_org_id,
        industry=bd.get("industry"),
        sub_industry=bd.get("sub_industry"),
        employee_count=str(bd.get("employee_count")) if bd.get("employee_count") else None,
        annual_revenue=bd.get("annual_revenue"),
        headquarters_country=bd.get("headquarters_country") or bd.get("headquarters", "").split(",")[0].strip() or None,
        headquarters_city=bd.get("headquarters_city") or (bd.get("headquarters", "").split(",")[1].strip() if "," in bd.get("headquarters", "") else None),
        ownership_type=bd.get("ownership_type"),
        regulatory_region=bd.get("regulatory_region"),
        website=bd.get("website"),
        functions=bd.get("functions", []),
        locations=bd.get("locations", []),
        processes=bd.get("processes", []),
        regulatory_frameworks=bd.get("regulatory_frameworks", []),
        notes=bd.get("notes"),
    )

    await audit_repo.log(
        api_name="business_demography_update",
        client_org_id=body.client_org_id,
        tenant_id=body.tenant_id,
        requested_by=body.updated_by,
        status="success",
        output_metadata={"demography_id": demo["id"]},
    )

    return ApiResponse(
        status="success",
        message="Business demography updated successfully",
        data={
            "client_org_id": body.client_org_id,
            "demography_record_id": demo["id"],
            "update_status": "completed",
        },
    )


async def get_demography(
    org_id: str,
    demo_repo: Annotated[DemographyRepository, Depends(get_demography_repo)],
) -> ApiResponse:
    demo = await demo_repo.get_by_org(org_id)
    if not demo:
        raise APIError("Demography not found", code="VALIDATION_ERROR", status_code=404)
    return ApiResponse(
        status="success",
        message="Demography retrieved",
        data=DemographyResponse(**demo).model_dump(),
    )


# ── API 2: Control Document Upload ────────────────────────────────────────────

async def upload_control_document(
    client_org_id: Annotated[str, Form()],
    tenant_id: Annotated[Optional[str], Form()] = None,
    uploaded_by: Annotated[Optional[str], Form()] = None,
    document_type: Annotated[Optional[str], Form()] = None,
    document_category: Annotated[Optional[str], Form()] = None,
    document_version: Annotated[Optional[str], Form()] = None,
    file: UploadFile = File(...),
    org_repo: OrgRepository = Depends(get_org_repo),
    folder_repo: FolderRepository = Depends(get_folder_repo),
    doc_repo: ControlDocumentRepository = Depends(get_control_document_repo),
    audit_repo: AuditLogRepository = Depends(get_audit_repo),
    settings: Settings = Depends(get_app_settings),
) -> ApiResponse:
    """API 2: Upload a control document to the org-specific folder."""
    # Validate org
    org = await org_repo.get_by_id(client_org_id)
    if not org:
        raise APIError("Organisation not found", code="CLIENT_ORG_NOT_FOUND", status_code=404)

    # Validate file type
    allowed = {".pdf", ".docx", ".xlsx", ".txt"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise APIError(
            f"File type {suffix} not allowed. Use: {', '.join(allowed)}",
            code="FILE_UPLOAD_FAILED",
            status_code=400,
        )

    folders = await sync_org_folder_mapping(
        settings,
        folder_repo,
        client_org_id=client_org_id,
        org_slug=str(org["slug"]),
    )
    ctrl_folder = folders["control_documents"]

    safe_name = Path(file.filename or "upload").name
    dest = Path(ctrl_folder).resolve() / safe_name
    content = await file.read()
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    except OSError as exc:
        raise APIError(
            f"Failed to write upload to {dest}: {exc}",
            code="FILE_UPLOAD_FAILED",
            status_code=500,
        ) from exc

    # Save metadata to database
    doc = await doc_repo.create(
        client_org_id=client_org_id,
        filename=safe_name,
        document_path=str(dest),
        document_type=document_type,
        document_category=document_category,
        document_version=document_version,
        uploaded_by=uploaded_by,
    )

    await audit_repo.log(
        api_name="control_document_upload",
        client_org_id=client_org_id,
        tenant_id=tenant_id,
        requested_by=uploaded_by,
        status="success",
        output_metadata={"document_id": doc["id"], "filename": safe_name},
    )

    return ApiResponse(
        status="success",
        message="Control document uploaded successfully",
        data=ControlDocumentResponse(**doc).model_dump(),
    )


async def list_control_documents(
    client_org_id: str,
    org_repo: Annotated[OrgRepository, Depends(get_org_repo)],
    folder_repo: Annotated[FolderRepository, Depends(get_folder_repo)],
    doc_repo: Annotated[ControlDocumentRepository, Depends(get_control_document_repo)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> ApiResponse:
    org = await org_repo.get_by_id(client_org_id)
    if not org:
        raise APIError("Organisation not found", code="CLIENT_ORG_NOT_FOUND", status_code=404)

    folders = await sync_org_folder_mapping(
        settings,
        folder_repo,
        client_org_id=client_org_id,
        org_slug=str(org["slug"]),
    )
    ctrl_folder = folders["control_documents"]

    docs = await doc_repo.list_for_org(client_org_id)
    out = []
    for d in docs:
        filename = str(d.get("filename") or "")
        resolved = resolve_file_in_folder(
            ctrl_folder,
            filename,
            str(d.get("document_path") or ""),
        )
        resolved_str = str(resolved)
        if resolved_str != str(d.get("document_path") or ""):
            await doc_repo.update_document_path(str(d["id"]), resolved_str)
        row = dict(d)
        row["document_path"] = resolved_str
        out.append(ControlDocumentResponse(**row).model_dump())

    return ApiResponse(
        status="success",
        message="Documents retrieved",
        data={"documents": out},
    )


# ── API 10: Risk Upload ────────────────────────────────────────────────────────

async def upload_risks(
    body: RiskUploadRequest,
    org_repo: Annotated[OrgRepository, Depends(get_org_repo)],
    risk_repo: Annotated[RiskRepository, Depends(get_risk_repo)],
    audit_repo: Annotated[AuditLogRepository, Depends(get_audit_repo)],
) -> ApiResponse:
    """API 10: Upload user-selected risks into the risk table."""
    org = await org_repo.get_by_id(body.client_org_id)
    if not org:
        raise APIError("Organisation not found", code="CLIENT_ORG_NOT_FOUND", status_code=404)

    created_ids = []
    for r in body.selected_risks:
        risk = await risk_repo.create(
            client_org_id=body.client_org_id,
            issue_id=r.issue_id,
            risk_title=r.risk_title,
            risk_description=r.risk_description,
            risk_rating=r.risk_rating,
            risk_score=r.risk_score,
            mapped_controls=r.mapped_controls,
            mapped_functions=r.mapped_functions,
            mapped_locations=r.mapped_locations,
            mapped_processes=r.mapped_processes,
            submitted_by=body.submitted_by,
        )
        created_ids.append(risk["id"])

    await audit_repo.log(
        api_name="risk_upload",
        client_org_id=body.client_org_id,
        tenant_id=body.tenant_id,
        requested_by=body.submitted_by,
        status="success",
        output_metadata={"risks_created": len(created_ids), "risk_ids": created_ids},
    )

    return ApiResponse(
        status="success",
        message="Selected risks uploaded successfully",
        data={
            "risks_received": len(body.selected_risks),
            "risks_created": len(created_ids),
            "risk_ids": created_ids,
        },
    )


async def list_risks(
    client_org_id: str,
    risk_repo: Annotated[RiskRepository, Depends(get_risk_repo)],
) -> ApiResponse:
    risks = await risk_repo.list_for_org(client_org_id)
    return ApiResponse(
        status="success",
        message="Risks retrieved",
        data={"risks": risks, "count": len(risks)},
    )