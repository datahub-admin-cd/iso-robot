from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from iso_robot.config import get_settings
from iso_robot.deps import get_folder_repo, get_org_repo, get_tenant_repo, get_user_repo, get_audit_repo, get_current_user
from iso_robot.domain.repair_storage_paths import sync_org_folder_mapping
from iso_robot.errors import APIError
from iso_robot.helpers.auth import create_token, hash_password, verify_password
from iso_robot.repositories.org_repository import (
    AuditLogRepository,
    FolderRepository,
    OrgRepository,
    TenantRepository,
    UserRepository,
)
from iso_robot.schemas.api import (
    ApiResponse,
    LoginData,
    LoginFolders,
    LoginRequest,
    UserCreateRequest,
    UserResponse,
)


async def login(
    body: LoginRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    org_repo: Annotated[OrgRepository, Depends(get_org_repo)],
    folder_repo: Annotated[FolderRepository, Depends(get_folder_repo)],
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repo)],
    audit_repo: Annotated[AuditLogRepository, Depends(get_audit_repo)],
) -> ApiResponse:
    """API 1: Login. Authenticates user and returns org, tenant, and folder context."""

    # Validate credentials
    user = await user_repo.get_by_email(body.username)
    if not user or not verify_password(body.password, user["hashed_password"]):
        await audit_repo.log(
            api_name="login",
            status="failed",
            input_metadata={"username": body.username},
            error_details="Invalid credentials",
        )
        raise APIError("Invalid username or password", code="AUTH_FAILED", status_code=401)

    if not user["is_active"]:
        raise APIError("Account is disabled", code="UNAUTHORIZED", status_code=403)

    # Get org details
    org = await org_repo.get_by_id(user["client_org_id"])
    if not org:
        raise APIError("Organisation not found", code="CLIENT_ORG_NOT_FOUND", status_code=404)

    # Get tenant mapping
    tenant = await tenant_repo.get_by_org(user["client_org_id"])
    tenant_id = tenant["tenant_id"] if tenant else None

    settings = get_settings()
    folders_raw = await sync_org_folder_mapping(
        settings,
        folder_repo,
        client_org_id=user["client_org_id"],
        org_slug=str(org["slug"]),
    )
    folders = LoginFolders(
        control_documents_folder=folders_raw.get("control_documents", ""),
        issues_folder=folders_raw.get("issues", ""),
        risk_outputs_folder=folders_raw.get("risk_outputs", ""),
    )

    # Create token
    token = create_token(user["id"], user["client_org_id"], user["role"])

    # Audit log
    await audit_repo.log(
        api_name="login",
        client_org_id=user["client_org_id"],
        tenant_id=tenant_id,
        requested_by=user["id"],
        status="success",
        input_metadata={"username": body.username, "login_source": body.login_source},
        output_metadata={"user_id": user["id"], "org": org["name"]},
    )

    return ApiResponse(
        status="success",
        message="Login successful",
        data=LoginData(
            access_token=token,
            user_id=user["id"],
            user_name=user.get("full_name"),
            client_org_id=user["client_org_id"],
            client_org_name=org["name"],
            tenant_id=tenant_id,
            folders=folders,
            roles=[user["role"]],
        ).model_dump(),
    )


async def register_user(
    body: UserCreateRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    org_repo: Annotated[OrgRepository, Depends(get_org_repo)],
) -> ApiResponse:
    """Register a new user. For demo/admin use only."""
    # Check org exists
    org = await org_repo.get_by_id(body.client_org_id)
    if not org:
        raise APIError("Organisation not found", code="CLIENT_ORG_NOT_FOUND", status_code=404)

    # Check no duplicate email
    existing = await user_repo.get_by_email(body.email)
    if existing:
        raise APIError("Email already registered", code="DUPLICATE_RECORD", status_code=409)

    hashed = hash_password(body.password)
    user = await user_repo.create(
        email=body.email,
        hashed_password=hashed,
        full_name=body.full_name,
        client_org_id=body.client_org_id,
        role=body.role,
    )

    return ApiResponse(
        status="success",
        message="User registered successfully",
        data=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user.get("full_name"),
            client_org_id=user["client_org_id"],
            role=user["role"],
            created_at=user["created_at"],
        ).model_dump(),
    )

async def me(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_repo: Annotated[OrgRepository, Depends(get_org_repo)],
) -> ApiResponse:
    """Validate the session and return the current user (also slides the window)."""
    org = await org_repo.get_by_id(current_user["client_org_id"])
    return ApiResponse(
        status="success",
        message="OK",
        data={
            "user_id": current_user["id"],
            "user_name": current_user.get("full_name"),
            "email": current_user["email"],
            "client_org_id": current_user["client_org_id"],
            "client_org_name": org["name"] if org else None,
            "roles": [current_user["role"]],
        },
    )