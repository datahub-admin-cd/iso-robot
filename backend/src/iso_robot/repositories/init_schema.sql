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