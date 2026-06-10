from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class DocumentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    filename: str
    path: str
    sha256: str
    mime_type: Optional[str] = None
    size_bytes: int
    framework: Optional[str] = None
    status: str
    source_url: Optional[str] = None
    created_at: str


class DocumentScanRequest(BaseModel):
    folder: Optional[str] = Field(
        default=None,
        description="Optional folder to scan; defaults to settings.DOCUMENTS_DIR",
    )


class DocumentScanResponse(BaseModel):
    scanned: int
    added: int
    updated: int
    skipped: int
    errors: List[str] = Field(default_factory=list)


class JobCreateRequest(BaseModel):
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    id: str
    type: str
    status: str
    payload: Dict[str, Any]
    error: Optional[str] = None
    created_at: str
    updated_at: str


class ControlListItem(BaseModel):
    id: str
    document_id: str
    client_org_id: Optional[str] = None
    control_text: Optional[str] = None
    section_ref: Optional[str] = None
    framework: Optional[str] = None
    source_page: Optional[int] = None
    created_at: str


class IssueListItem(BaseModel):
    id: str
    risk_source_id: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    effective_date: Optional[str] = None
    region_hint: Optional[str] = None
    created_at: str
    classification: Optional[Dict[str, Any]] = None
    issue_scope: Optional[str] = Field(
        default=None,
        description="internal | external when derived from controls payload.",
    )
    sector: Optional[str] = None
    source_document_id: Optional[str] = None
    control_ids: Optional[List[str]] = None
    origin: Optional[str] = Field(default=None, description="e.g. from_controls")
    client_org_id: Optional[str] = None


class CandidateRiskListItem(BaseModel):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    confidence: Optional[float] = None
    created_at: str
    issue_ids: List[str] = Field(default_factory=list)
    match_status: Optional[str] = None
    library_risk_id: Optional[str] = None
    match_rationale: Optional[str] = None
    bm25_score: Optional[float] = None


class RiskLibraryListItem(BaseModel):
    id: str
    industry: Optional[str] = None
    risk_domain: Optional[str] = None
    title: str
    description: Optional[str] = None
    tags: Optional[str] = None
    source_ref: Optional[str] = None
    created_at: str


class DiscoveryExportResponse(BaseModel):
    documents_summary: Dict[str, Any] = Field(default_factory=dict)
    controls: List[ControlListItem] = Field(default_factory=list)
    issues: List[IssueListItem] = Field(default_factory=list)
    candidate_risks: List[CandidateRiskListItem] = Field(default_factory=list)
    risk_library_matches: List[Dict[str, Any]] = Field(default_factory=list)
    risk_library: List[RiskLibraryListItem] = Field(default_factory=list)


class DashboardSummaryResponse(BaseModel):
    documents: int
    controls: int
    issues: int
    candidate_risks: int
    risk_library: int
    jobs_running: int


class ExtractControlsRequest(BaseModel):
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="If omitted, all PDFs in the documents table are processed.",
    )


class ExtractControlsForOrgRequest(BaseModel):
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional subset of document UUIDs; default = all PDFs in org folder.",
    )
    tenant_id: Optional[str] = None
    requested_by: Optional[str] = None


class ClassifyIssuesRequest(BaseModel):
    issue_ids: Optional[List[str]] = Field(
        default=None,
        description="If omitted, classify issues that have no classification row yet.",
    )


class IssuesFromControlsRequest(BaseModel):
    replace_existing: bool = Field(
        default=True,
        description="Remove prior issues with origin=from_controls for this organisation before inserting.",
    )
    classify_after: bool = Field(
        default=True,
        description="Run classification for newly created issue ids in the same job.",
    )
    sector_hint: Optional[str] = Field(default=None, description="Optional sector label passed to the model.")
    region_hint: Optional[str] = Field(default=None, description="Default region_hint when the model omits it.")


class IssueClassificationResponse(BaseModel):
    issue_id: str
    classification: Dict[str, Any]
    model_version: Optional[str] = None
    created_at: Optional[str] = None


class SeedPocResponse(BaseModel):
    risk_sources: int
    issues: int
    poc_path: str


class SeedRiskLibraryResponse(BaseModel):
    entries: int
    csv_path: str


class IssuesImportResponse(BaseModel):
    created: int
    errors: List[str] = Field(default_factory=list)

# =============================================================================
# NEW SCHEMAS — Risk Portal API Delivery
# =============================================================================

# ── Standard API Response Wrapper ─────────────────────────────────────────────

class ApiResponse(BaseModel):
    """Standard response wrapper used by all new APIs."""
    status: str = "success"
    message: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., description="User email address")
    password: str
    login_source: Optional[str] = Field(default="web_portal")


class LoginFolders(BaseModel):
    control_documents_folder: str
    issues_folder: str
    risk_outputs_folder: str


class LoginData(BaseModel):
    access_token: str
    user_id: str
    user_name: Optional[str] = None
    client_org_id: str
    client_org_name: Optional[str] = None
    tenant_id: Optional[str] = None
    folders: Optional[LoginFolders] = None
    roles: List[str] = Field(default_factory=list)


# ── Organisation ──────────────────────────────────────────────────────────────

class OrgCreateRequest(BaseModel):
    name: str
    slug: str
    industry: Optional[str] = None
    region: Optional[str] = None


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    industry: Optional[str] = None
    region: Optional[str] = None
    created_at: str


# ── User Registration ─────────────────────────────────────────────────────────

class UserCreateRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    client_org_id: str
    role: str = "analyst"


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    client_org_id: str
    role: str
    created_at: str


# ── Business Demography ───────────────────────────────────────────────────────

class LocationItem(BaseModel):
    country: str
    city: Optional[str] = None
    location_type: Optional[str] = None


class ProcessItem(BaseModel):
    process_name: str
    process_owner: Optional[str] = None


class DemographyUpdateRequest(BaseModel):
    client_org_id: str
    tenant_id: Optional[str] = None
    updated_by: Optional[str] = None
    business_demography: Dict[str, Any] = Field(default_factory=dict)


class DemographyResponse(BaseModel):
    id: str
    client_org_id: str
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    employee_count: Optional[str] = None
    annual_revenue: Optional[str] = None
    headquarters_country: Optional[str] = None
    headquarters_city: Optional[str] = None
    ownership_type: Optional[str] = None
    regulatory_region: Optional[str] = None
    website: Optional[str] = None
    functions: List[Any] = Field(default_factory=list)
    locations: List[Any] = Field(default_factory=list)
    processes: List[Any] = Field(default_factory=list)
    regulatory_frameworks: List[Any] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: str
    updated_at: str


# ── Control Document Upload ───────────────────────────────────────────────────

class ControlDocumentResponse(BaseModel):
    id: str
    client_org_id: str
    filename: str
    document_path: str
    document_type: Optional[str] = None
    document_category: Optional[str] = None
    document_version: Optional[str] = None
    processing_status: str
    created_at: str


# ── Issue Scoring ─────────────────────────────────────────────────────────────

class IssueScoreRequest(BaseModel):
    client_org_id: str
    tenant_id: Optional[str] = None
    requested_by: Optional[str] = None
    issue_ids: Optional[List[str]] = None
    scoring_framework_id: Optional[str] = None


# ── Risk Upload ───────────────────────────────────────────────────────────────

class SelectedRisk(BaseModel):
    issue_id: Optional[str] = None
    risk_title: str
    risk_description: Optional[str] = None
    risk_rating: Optional[str] = None
    risk_score: Optional[int] = None
    mapped_controls: List[str] = Field(default_factory=list)
    mapped_functions: List[str] = Field(default_factory=list)
    mapped_locations: List[str] = Field(default_factory=list)
    mapped_processes: List[str] = Field(default_factory=list)
    user_action: Optional[str] = None


class RiskUploadRequest(BaseModel):
    client_org_id: str
    tenant_id: Optional[str] = None
    submitted_by: Optional[str] = None
    selected_risks: List[SelectedRisk]


class RiskResponse(BaseModel):
    id: str
    client_org_id: str
    issue_id: Optional[str] = None
    risk_title: str
    risk_description: Optional[str] = None
    risk_rating: Optional[str] = None
    risk_score: Optional[int] = None
    created_at: str


class ScoreRisksRequest(BaseModel):
    issue_ids: Optional[List[str]] = None
    controls: Optional[List[str]] = None


class RiskAssessmentResponse(BaseModel):
    issue_id: str
    model_version: Optional[str] = None
    created_at: str
    assessment: Dict[str, Any]