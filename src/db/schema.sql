CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT DEFAULT 'OPEN'
);


CREATE TABLE IF NOT EXISTS evidence_files (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(id),
  path TEXT NOT NULL,
  original_md5 TEXT NOT NULL,
  original_sha256 TEXT NOT NULL,
  derived_md5 TEXT,
  derived_sha256 TEXT,
  size_bytes INTEGER NOT NULL,
  file_type TEXT NOT NULL,
  vendor TEXT NOT NULL,
  captured_at TEXT,
  status TEXT NOT NULL,
  validation_confidence TEXT NOT NULL CHECK (validation_confidence IN ('Validated: Real Device','Validated: Synthetic Reference Data','Stub: Awaiting Hardware'))
);

CREATE TABLE IF NOT EXISTS timeline_events (
  id TEXT PRIMARY KEY,
  evidence_file_id TEXT NOT NULL REFERENCES evidence_files(id),
  channel INTEGER,
  event_time TEXT NOT NULL,
  precision TEXT NOT NULL CHECK (precision IN ('exact','approximate')),
  confidence_window_seconds INTEGER,
  description TEXT
);
