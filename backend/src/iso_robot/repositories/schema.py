from pathlib import Path

import aiosqlite

_RISKS_STAGE_COLUMNS: dict[str, str] = {
    "process_tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "function_tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "department_tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "kpi_tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "region_tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "control_family_tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "tag_status": "TEXT NOT NULL DEFAULT 'untagged'",
    "owner_user_id": "TEXT",
    "accountable_user_id": "TEXT",
    "owner_assignment_status": "TEXT NOT NULL DEFAULT 'unassigned'",
    "updated_at": "TEXT",
}


async def _migrate_risks_columns(conn: aiosqlite.Connection) -> None:
    cur = await conn.execute("PRAGMA table_info(risks)")
    rows = await cur.fetchall()
    existing = {str(r[1]) for r in rows}
    for column, ddl in _RISKS_STAGE_COLUMNS.items():
        if column not in existing:
            await conn.execute(f"ALTER TABLE risks ADD COLUMN {column} {ddl}")


async def ensure_schema(conn: aiosqlite.Connection) -> None:
    """Apply `init_schema.sql` DDL plus idempotent column migrations."""
    sql_path = Path(__file__).resolve().parent / "init_schema.sql"
    script = sql_path.read_text(encoding="utf-8")
    await conn.executescript(script)
    await _migrate_risks_columns(conn)
    await conn.commit()
