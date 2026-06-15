PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────────────────────────────────────
-- EXISTING TABLES (kept exactly as they were, with client_org_id added)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL UNIQUE,
  mime_type TEXT,
  size_bytes INTEGER NOT NULL,
  framework TEXT,
  status TEXT NOT NULL DEFAULT 'local',
  source_url TEXT,
  client_org_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_org ON documents(client_org_id);

CREATE TABLE IF NOT EXISTS controls (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  control_text TEXT,
  section_ref TEXT,
  framework TEXT,
  source_page INTEGER,
  client_org_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_controls_document_id ON controls(document_id);
CREATE INDEX IF NOT EXISTS idx_controls_org ON controls(client_org_id);

CREATE TABLE IF NOT EXISTS risk_sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  source_type TEXT,
  url TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  client_org_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS issues (
  id TEXT PRIMARY KEY,
  risk_source_id TEXT,
  title TEXT,
  body TEXT,
  effective_date TEXT,
  region_hint TEXT,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  client_org_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (risk_source_id) REFERENCES risk_sources(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_issues_risk_source_id ON issues(risk_source_id);
CREATE INDEX IF NOT EXISTS idx_issues_org ON issues(client_org_id);

CREATE TABLE IF NOT EXISTS issue_classifications (
  id TEXT PRIMARY KEY,
  issue_id TEXT NOT NULL,
  classification_json TEXT NOT NULL,
  model_version TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_issue_classifications_issue_id ON issue_classifications(issue_id);

CREATE TABLE IF NOT EXISTS candidate_risks (
  id TEXT PRIMARY KEY,
  issue_ids_json TEXT NOT NULL DEFAULT '[]',
  title TEXT,
  description TEXT,
  domain TEXT,
  confidence REAL,
  client_org_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS risk_library (
  id TEXT PRIMARY KEY,
  industry TEXT,
  risk_domain TEXT,
  title TEXT NOT NULL,
  description TEXT,
  tags TEXT,
  source_ref TEXT,
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS risk_discovery_results (
  id TEXT PRIMARY KEY,
  candidate_risk_id TEXT,
  library_risk_id TEXT,
  match_status TEXT,
  rationale TEXT,
  bm25_score REAL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (candidate_risk_id) REFERENCES candidate_risks(id) ON DELETE CASCADE,
  FOREIGN KEY (library_risk_id) REFERENCES risk_library(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_risk_discovery_candidate ON risk_discovery_results(candidate_risk_id);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- NEW TABLES
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS client_organizations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  industry TEXT,
  region TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  hashed_password TEXT NOT NULL,
  full_name TEXT,
  client_org_id TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'analyst',
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (client_org_id) REFERENCES client_organizations(id)
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_org ON users(client_org_id);

CREATE TABLE IF NOT EXISTS tenant_mapping (
  id TEXT PRIMARY KEY,
  client_org_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (client_org_id) REFERENCES client_organizations(id)
);

CREATE TABLE IF NOT EXISTS folder_mapping (
  id TEXT PRIMARY KEY,
  client_org_id TEXT NOT NULL,
  folder_type TEXT NOT NULL,
  folder_path TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (client_org_id) REFERENCES client_organizations(id)
);

CREATE INDEX IF NOT EXISTS idx_folder_mapping_org ON folder_mapping(client_org_id);

CREATE TABLE IF NOT EXISTS business_demography (
  id TEXT PRIMARY KEY,
  client_org_id TEXT NOT NULL UNIQUE,
  industry TEXT,
  sub_industry TEXT,
  employee_count TEXT,
  annual_revenue TEXT,
  headquarters_country TEXT,
  headquarters_city TEXT,
  ownership_type TEXT,
  regulatory_region TEXT,
  website TEXT,
  functions_json TEXT NOT NULL DEFAULT '[]',
  locations_json TEXT NOT NULL DEFAULT '[]',
  processes_json TEXT NOT NULL DEFAULT '[]',
  regulatory_frameworks_json TEXT NOT NULL DEFAULT '[]',
  notes TEXT,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (client_org_id) REFERENCES client_organizations(id)
);

CREATE TABLE IF NOT EXISTS control_documents (
  id TEXT PRIMARY KEY,
  client_org_id TEXT NOT NULL,
  filename TEXT NOT NULL,
  document_path TEXT NOT NULL,
  document_type TEXT,
  document_category TEXT,
  document_version TEXT,
  uploaded_by TEXT,
  processing_status TEXT NOT NULL DEFAULT 'ready_for_extraction',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (client_org_id) REFERENCES client_organizations(id)
);

CREATE INDEX IF NOT EXISTS idx_control_documents_org ON control_documents(client_org_id);

CREATE TABLE IF NOT EXISTS issue_scores (
  id TEXT PRIMARY KEY,
  issue_id TEXT NOT NULL,
  client_org_id TEXT,
  risk_score INTEGER,
  risk_rating TEXT,
  likelihood_score INTEGER,
  impact_score INTEGER,
  velocity_score INTEGER,
  mapped_functions_json TEXT NOT NULL DEFAULT '[]',
  mapped_locations_json TEXT NOT NULL DEFAULT '[]',
  mapped_processes_json TEXT NOT NULL DEFAULT '[]',
  recommended_risk_title TEXT,
  scoring_run_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_issue_scores_issue ON issue_scores(issue_id);
CREATE INDEX IF NOT EXISTS idx_issue_scores_org ON issue_scores(client_org_id);

CREATE TABLE IF NOT EXISTS risks (
  id TEXT PRIMARY KEY,
  client_org_id TEXT NOT NULL,
  issue_id TEXT,
  risk_title TEXT NOT NULL,
  risk_description TEXT,
  risk_rating TEXT,
  risk_score INTEGER,
  mapped_controls_json TEXT NOT NULL DEFAULT '[]',
  mapped_functions_json TEXT NOT NULL DEFAULT '[]',
  mapped_locations_json TEXT NOT NULL DEFAULT '[]',
  mapped_processes_json TEXT NOT NULL DEFAULT '[]',
  submitted_by TEXT,
  process_tags_json TEXT NOT NULL DEFAULT '[]',
  function_tags_json TEXT NOT NULL DEFAULT '[]',
  department_tags_json TEXT NOT NULL DEFAULT '[]',
  kpi_tags_json TEXT NOT NULL DEFAULT '[]',
  region_tags_json TEXT NOT NULL DEFAULT '[]',
  control_family_tags_json TEXT NOT NULL DEFAULT '[]',
  tag_status TEXT NOT NULL DEFAULT 'untagged',
  owner_user_id TEXT,
  accountable_user_id TEXT,
  owner_assignment_status TEXT NOT NULL DEFAULT 'unassigned',
  updated_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (client_org_id) REFERENCES client_organizations(id),
  FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_risks_org ON risks(client_org_id);

CREATE TABLE IF NOT EXISTS api_audit_log (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  api_name TEXT NOT NULL,
  client_org_id TEXT,
  tenant_id TEXT,
  requested_by TEXT,
  request_timestamp TEXT NOT NULL,
  completion_timestamp TEXT,
  status TEXT,
  input_metadata_json TEXT NOT NULL DEFAULT '{}',
  output_metadata_json TEXT NOT NULL DEFAULT '{}',
  error_details TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_org ON api_audit_log(client_org_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON api_audit_log(request_timestamp);

CREATE TABLE IF NOT EXISTS risk_assessments (
  id TEXT PRIMARY KEY,
  issue_id TEXT NOT NULL,
  risk_type TEXT,
  likelihood TEXT,
  consequence TEXT,
  velocity TEXT,
  inherent_risk TEXT,
  overall_control_effectiveness TEXT,
  residual_risk TEXT,
  risk_response TEXT,
  assessment_json TEXT NOT NULL,
  model_version TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_assessments_issue ON risk_assessments(issue_id);

CREATE TABLE IF NOT EXISTS issue_controls (
  issue_id TEXT NOT NULL,
  control_id TEXT NOT NULL,
  PRIMARY KEY (issue_id, control_id),
  FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
  FOREIGN KEY (control_id) REFERENCES controls(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_issue_controls_issue ON issue_controls(issue_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- STAGE 09 / 10 TABLES — Risk Tagging and Risk Owner Assignment
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS catalog_items (
  id TEXT PRIMARY KEY,
  client_org_id TEXT NOT NULL,
  catalog_id TEXT NOT NULL,
  dimension TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  keywords_json TEXT NOT NULL DEFAULT '[]',
  criticality TEXT NOT NULL DEFAULT 'standard',
  owner_user_id TEXT,
  catalog_version TEXT NOT NULL DEFAULT 'v1',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (client_org_id) REFERENCES client_organizations(id)
);

CREATE INDEX IF NOT EXISTS idx_catalog_items_org_dim ON catalog_items(client_org_id, dimension);
CREATE INDEX IF NOT EXISTS idx_catalog_items_catalog ON catalog_items(catalog_id);

CREATE TABLE IF NOT EXISTS org_hierarchy_snapshots (
  id TEXT PRIMARY KEY,
  client_org_id TEXT NOT NULL,
  snapshot_status TEXT NOT NULL DEFAULT 'approved',
  source TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (client_org_id) REFERENCES client_organizations(id)
);

CREATE INDEX IF NOT EXISTS idx_hierarchy_snapshots_org ON org_hierarchy_snapshots(client_org_id);

CREATE TABLE IF NOT EXISTS org_hierarchy_users (
  id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL,
  client_org_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  name TEXT,
  email TEXT,
  title TEXT,
  function TEXT,
  department TEXT,
  region TEXT,
  management_level TEXT,
  manager_user_id TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  ownership_roles_json TEXT NOT NULL DEFAULT '[]',
  owned_process_ids_json TEXT NOT NULL DEFAULT '[]',
  owned_kpi_ids_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (snapshot_id) REFERENCES org_hierarchy_snapshots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hierarchy_users_snapshot ON org_hierarchy_users(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_hierarchy_users_org ON org_hierarchy_users(client_org_id);

CREATE TABLE IF NOT EXISTS risk_tags (
  id TEXT PRIMARY KEY,
  client_org_id TEXT NOT NULL,
  risk_id TEXT NOT NULL,
  process_tags_json TEXT NOT NULL DEFAULT '[]',
  function_tags_json TEXT NOT NULL DEFAULT '[]',
  department_tags_json TEXT NOT NULL DEFAULT '[]',
  kpi_tags_json TEXT NOT NULL DEFAULT '[]',
  region_tags_json TEXT NOT NULL DEFAULT '[]',
  control_family_tags_json TEXT NOT NULL DEFAULT '[]',
  tag_status TEXT NOT NULL DEFAULT 'proposed',
  confidence REAL,
  rationale TEXT,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  inputs_json TEXT NOT NULL DEFAULT '{}',
  catalog_version TEXT,
  run_job_id TEXT,
  auto_applied INTEGER NOT NULL DEFAULT 0,
  reviewer_user_id TEXT,
  reviewer_notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (client_org_id) REFERENCES client_organizations(id),
  FOREIGN KEY (risk_id) REFERENCES risks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_tags_org ON risk_tags(client_org_id);
CREATE INDEX IF NOT EXISTS idx_risk_tags_risk ON risk_tags(risk_id);
CREATE INDEX IF NOT EXISTS idx_risk_tags_status ON risk_tags(tag_status);

CREATE TABLE IF NOT EXISTS risk_assignments (
  id TEXT PRIMARY KEY,
  client_org_id TEXT NOT NULL,
  risk_id TEXT NOT NULL,
  recommended_owner_user_id TEXT,
  recommended_owner_json TEXT NOT NULL DEFAULT '{}',
  alternate_owners_json TEXT NOT NULL DEFAULT '[]',
  accountable_user_id TEXT,
  assignment_type TEXT,
  assignment_status TEXT NOT NULL DEFAULT 'proposed',
  confidence REAL,
  matched_on_json TEXT NOT NULL DEFAULT '[]',
  rationale TEXT,
  inputs_json TEXT NOT NULL DEFAULT '{}',
  hierarchy_snapshot_id TEXT,
  run_job_id TEXT,
  auto_applied INTEGER NOT NULL DEFAULT 0,
  reviewer_user_id TEXT,
  reviewer_notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (client_org_id) REFERENCES client_organizations(id),
  FOREIGN KEY (risk_id) REFERENCES risks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_assignments_org ON risk_assignments(client_org_id);
CREATE INDEX IF NOT EXISTS idx_risk_assignments_risk ON risk_assignments(risk_id);
CREATE INDEX IF NOT EXISTS idx_risk_assignments_status ON risk_assignments(assignment_status);