import os
import sys
import shutil
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from src.db.connection import get_connection
from src.pipeline.dispatch import dispatch_pipeline


db_path = Path("evidence_store/forensic.db")
db_path.unlink(missing_ok=True)

# Clean out evidence_store case directories except sample_data
for item in Path("evidence_store").glob("case_*"):
    if item.is_dir():
        shutil.rmtree(item, ignore_errors=True)

conn = get_connection(db_path)
cursor = conn.cursor()
cursor.execute(
    "INSERT INTO cases (id, name, created_at, status) VALUES (?, ?, ?, ?)",
    ("case_001", "Surveillance Investigation #101", "2026-09-07T12:00:00Z", "OPEN")
)
conn.commit()

res = dispatch_pipeline(
    file_path=Path("sample_data/sample_dahua_clean.dav"),
    case_id="case_001",
    db_conn=conn,
    validation_confidence="Validated: Synthetic Reference Data"
)
conn.close()
print("DB RESET SUCCESSFUL. Single case with single file created:", res)
