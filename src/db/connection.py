import sqlite3
from pathlib import Path
from typing import Union

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: Union[str, Path]) -> sqlite3.Connection:
    """
    Establishes a connection to the SQLite database at `db_path`,
    enforces WAL journal mode and foreign key constraints,
    and applies `schema.sql` idempotently.
    """
    db_path = Path(db_path)
    if db_path != Path(":memory:"):
        db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Execute mandatory WAL mode and Foreign Keys PRAGMAs on every connection
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")

    # Load and execute schema
    if SCHEMA_PATH.exists():
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
    else:
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_PATH}")

    return conn
