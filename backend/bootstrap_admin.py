"""One-off DEV tool: create the platform admin. Not part of app runtime.
Run from the `backend/` folder with PYTHONPATH=src. Password from ADMIN_PASSWORD env var.
Do NOT commit a real password."""
import asyncio
import os
from pathlib import Path

import aiosqlite

from dotenv import load_dotenv
load_dotenv()

from iso_robot.config import get_settings
from iso_robot.helpers.auth import hash_password
from iso_robot.repositories.org_repository import OrgRepository, UserRepository

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")   # override via env for anything real
PLATFORM_SLUG = "platform"


async def main() -> None:
    settings = get_settings()
    conn = await aiosqlite.connect(str(settings.resolved_database_path()))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        # ensure tables exist (safe to re-run; uses CREATE TABLE IF NOT EXISTS)
        schema = Path(__file__).resolve().parent / "src" / "iso_robot" / "repositories" / "init_schema.sql"
        await conn.executescript(schema.read_text(encoding="utf-8"))

        orgs = OrgRepository(conn)
        users = UserRepository(conn)

        platform = await orgs.get_by_slug(PLATFORM_SLUG)
        if not platform:
            platform = await orgs.create(name="Platform (internal)", slug=PLATFORM_SLUG,
                                         industry="internal", region="internal")
            print("Created platform org:", platform["id"])
        else:
            print("Platform org exists:", platform["id"])

        if await users.get_by_email(ADMIN_EMAIL):
            print("Admin already exists:", ADMIN_EMAIL); return
        admin = await users.create(email=ADMIN_EMAIL, hashed_password=hash_password(ADMIN_PASSWORD),
                                   full_name="Platform Admin", client_org_id=platform["id"], role="admin")
        print("Created admin:", admin["id"], "| email:", ADMIN_EMAIL)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())