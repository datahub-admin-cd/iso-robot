"""Seed the demo analyst users (one per org). Idempotent: safe to re-run.
Run from backend/ with PYTHONPATH=src. Dev tool — not used at runtime."""
import asyncio

import aiosqlite

from iso_robot.config import get_settings
from iso_robot.helpers.auth import hash_password
from iso_robot.repositories.org_repository import OrgRepository, UserRepository

DEMO_USERS = [
    {"slug": "ORG001", "email": "qoc@demo.local",       "full_name": "QOC Analyst",       "password": "Passw0rd!"},
    {"slug": "ORG002", "email": "energy@demo.local",    "full_name": "Energy Analyst",    "password": "Passw0rd!"},
    {"slug": "ORG003", "email": "transport@demo.local", "full_name": "Transport Analyst", "password": "Passw0rd!"},
]


async def main() -> None:
    conn = await aiosqlite.connect(str(get_settings().resolved_database_path()))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        orgs = OrgRepository(conn)
        users = UserRepository(conn)
        for u in DEMO_USERS:
            org = await orgs.get_by_slug(u["slug"])
            if not org:
                print(f"SKIP {u['email']}: org {u['slug']} not found"); continue
            if await users.get_by_email(u["email"]):
                print(f"exists  {u['email']}"); continue
            row = await users.create(
                email=u["email"], hashed_password=hash_password(u["password"]),
                full_name=u["full_name"], client_org_id=org["id"], role="analyst",
            )
            print(f"created {u['email']}  ({u['slug']} -> {row['id']})")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())