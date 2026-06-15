from __future__ import annotations

from fastapi import APIRouter

from iso_robot.handlers import (
    classifications,
    controls,
    documents,
    export,
    health,
    issues,
    jobs,
    risk,
    summary,
    system_hints,
)
from iso_robot.handlers import auth, org, controls_org
from iso_robot.handlers import risk_assignment, risk_tagging

router = APIRouter()

# ── Existing routes (DO NOT CHANGE) ──────────────────────────────────────────

router.add_api_route("/health", health.health, methods=["GET"], tags=["health"])
router.add_api_route("/summary", summary.dashboard_summary, methods=["GET"], tags=["summary"])
router.add_api_route("/system/status", system_hints.system_status, methods=["GET"], tags=["system"])

router.add_api_route("/documents", documents.list_documents, methods=["GET"], tags=["documents"])
router.add_api_route("/documents/scan", documents.scan_documents, methods=["POST"], tags=["documents"])
router.add_api_route("/documents/{doc_id}/file", documents.get_document_file, methods=["GET"], tags=["documents"])
router.add_api_route("/documents/{doc_id}", documents.get_document, methods=["GET"], tags=["documents"])

router.add_api_route("/jobs", jobs.create_job_handler, methods=["POST"], tags=["jobs"])
router.add_api_route("/jobs", jobs.list_jobs_handler, methods=["GET"], tags=["jobs"])
router.add_api_route("/jobs/{job_id}", jobs.get_job_handler, methods=["GET"], tags=["jobs"])

router.add_api_route("/controls", controls.list_controls, methods=["GET"], tags=["controls"])
router.add_api_route("/controls/extract", controls.extract_controls, methods=["POST"], tags=["controls"])

router.add_api_route("/issues", issues.list_issues, methods=["GET"], tags=["issues"])
router.add_api_route("/issues/seed-from-poc", issues.seed_issues_from_poc, methods=["POST"], tags=["issues"])
router.add_api_route("/issues/import-csv", issues.import_issues_csv, methods=["POST"], tags=["issues"])
router.add_api_route("/issues/classify", issues.classify_issues, methods=["POST"], tags=["issues"])
router.add_api_route(
    "/issues/from-controls/{client_org_id}",
    issues.issues_from_controls,
    methods=["POST"],
    tags=["issues"],
)
router.add_api_route("/issues/stats/{client_org_id}", issues.issue_stats_for_org, methods=["GET"], tags=["issues"])
router.add_api_route("/issues/{issue_id}", issues.get_issue, methods=["GET"], tags=["issues"])
router.add_api_route(
    "/issues/{issue_id}/classification",
    issues.get_issue_classification,
    methods=["GET"],
    tags=["issues"],
)

router.add_api_route(
    "/classifications/aggregate",
    classifications.aggregate,
    methods=["GET"],
    tags=["classifications"],
)

router.add_api_route("/risk-library", risk.list_risk_library, methods=["GET"], tags=["risk-library"])
router.add_api_route("/risk-library/seed-from-poc", risk.seed_risk_library_handler, methods=["POST"], tags=["risk-library"])

router.add_api_route("/candidate-risks", risk.list_candidate_risks, methods=["GET"], tags=["risk-discovery"])
router.add_api_route("/risk-discovery/run", risk.run_risk_discovery, methods=["POST"], tags=["risk-discovery"])
router.add_api_route("/risk-scoring/run", risk.run_risk_scoring, methods=["POST"], tags=["risk-scoring"])
router.add_api_route(
    "/issues/{issue_id}/risk-assessment",
    risk.get_issue_risk_assessment,
    methods=["GET"],
    tags=["risk-scoring"],
)

router.add_api_route("/discovery-export", export.discovery_export, methods=["GET"], tags=["export"])

# ── NEW ROUTES — Risk Portal API Delivery ─────────────────────────────────────

# Auth (API 1)
router.add_api_route("/auth/login", auth.login, methods=["POST"], tags=["auth"])
router.add_api_route("/auth/register", auth.register_user, methods=["POST"], tags=["auth"])
router.add_api_route("/auth/me", auth.me, methods=["GET"], tags=["auth"])

# Organisations
router.add_api_route("/orgs", org.create_org, methods=["POST"], tags=["orgs"])
router.add_api_route("/orgs", org.list_orgs, methods=["GET"], tags=["orgs"])

# Control Documents (API 2)
router.add_api_route("/control-documents/upload", org.upload_control_document, methods=["POST"], tags=["control-documents"])
router.add_api_route("/control-documents/stats/{client_org_id}", controls_org.control_stats_for_org, methods=["GET"], tags=["control-documents"])
router.add_api_route("/control-documents/{client_org_id}", org.list_control_documents, methods=["GET"], tags=["control-documents"])

# Business Demography (API 3)
router.add_api_route("/business-demography/update", org.update_demography, methods=["POST"], tags=["business-demography"])
router.add_api_route("/business-demography/{org_id}", org.get_demography, methods=["GET"], tags=["business-demography"])

# Org-aware Control Extraction (API 4 — Newrequirement)
router.add_api_route("/control-documents/extract/{client_org_id}", controls_org.extract_controls_for_org, methods=["POST"], tags=["control-extraction"])

# Risk Upload (API 10)
router.add_api_route("/risks/upload-selected", org.upload_risks, methods=["POST"], tags=["risks"])

# ── Stage 09 — Risk Tagging ───────────────────────────────────────────────────
router.add_api_route("/risks/untagged", risk_tagging.list_untagged_risks, methods=["GET"], tags=["risk-tagging"])
router.add_api_route("/risk-tagging/run", risk_tagging.run_risk_tagging, methods=["POST"], status_code=202, tags=["risk-tagging"])
router.add_api_route("/risk-tags", risk_tagging.list_risk_tags, methods=["GET"], tags=["risk-tagging"])
router.add_api_route("/risk-tagging/apply-selected", risk_tagging.apply_selected_tags, methods=["POST"], tags=["risk-tagging"])
router.add_api_route("/risk-tagging/kpis", risk_tagging.risk_tagging_kpis, methods=["GET"], tags=["risk-tagging"])

# ── Stage 10 — Risk Owner Assignment ──────────────────────────────────────────
router.add_api_route("/risks/unassigned", risk_assignment.list_unassigned_risks, methods=["GET"], tags=["risk-assignment"])
router.add_api_route("/risk-assignments/run", risk_assignment.run_risk_assignment, methods=["POST"], status_code=202, tags=["risk-assignment"])
router.add_api_route("/risk-assignments/kpis", risk_assignment.risk_assignment_kpis, methods=["GET"], tags=["risk-assignment"])
router.add_api_route("/risk-assignments/apply-selected", risk_assignment.apply_selected_assignments, methods=["POST"], tags=["risk-assignment"])
router.add_api_route("/risk-assignments", risk_assignment.list_risk_assignments, methods=["GET"], tags=["risk-assignment"])
router.add_api_route("/organisation-hierarchy/{org_id}", risk_assignment.get_organisation_hierarchy, methods=["GET"], tags=["organisation-hierarchy"])

router.add_api_route("/risks/{client_org_id}", org.list_risks, methods=["GET"], tags=["risks"])