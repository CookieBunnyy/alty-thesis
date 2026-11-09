"""Start the system from zero for a demo: delete every record and keep one
Administrator account.

    python scripts/reset_demo_data.py --yes                      # the DATABASE_URL in .env
    python scripts/reset_demo_data.py --yes --database-url "postgresql://..."

What happens:
1. A full backup (pg_dump, custom format) is written to --backup-dir first.
   Without a backup the script stops, unless --no-backup is given.
   Restore with:  pg_restore --clean --if-exists -d "<database url>" <file>
2. Every table is emptied and its numbering restarts at 1 (users included), except:
   alembic_version (schema version), roles, document_schemas (commission
   voucher fields) and document_folders (the repository's folder structure).
3. One account is created: username "admin", role Administrator, with the
   password from --admin-password (default "admin1234"; change it after the
   demo).

Not touched: files in storage (Supabase Storage / local folder). They are no
longer referenced and are harmless. The central website tables used by the
"Sync" buttons are not changed either: pressing Sync after a reset brings
those records back.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

KEEP = {"alembic_version", "roles", "document_schemas", "document_folders"}


def _pg_dump() -> str | None:
    found = shutil.which("pg_dump")
    if found:
        return found
    candidates = sorted(glob.glob(r"C:\Program Files\PostgreSQL\*\bin\pg_dump.exe"), reverse=True)
    return candidates[0] if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="really delete every record")
    parser.add_argument("--database-url", help="defaults to DATABASE_URL from .env")
    # Outside the repository, so a backup (it holds personal data) is never committed.
    parser.add_argument("--backup-dir", default=str(Path.home() / "alty-backups"))
    parser.add_argument("--no-backup", action="store_true", help="skip the backup (not recommended)")
    parser.add_argument("--admin-password", default="admin1234")
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    from sqlalchemy import inspect, text
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401  (every model, so relationships resolve)
    from app.core.database import engine
    from app.models.audit import AuditEvent
    from app.models.user import User
    from app.core.security import ADMINISTRATOR, get_password_hash

    url = engine.url  # (str(url) would hide the password)
    print(f"Target database: {url.database} on {url.host}")
    if not args.yes:
        print("Nothing changed. Run again with --yes to delete every record.")
        return 1
    if len(args.admin_password) < 8:
        print("The admin password must be at least 8 characters.")
        return 1

    if not args.no_backup:
        dump = _pg_dump()
        if not dump:
            print("pg_dump wasn't found, so no backup can be made. Install the PostgreSQL client tools, "
                  "or pass --no-backup.")
            return 1
        backup_dir = Path(args.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = backup_dir / f"{url.database}-{datetime.now():%Y%m%d-%H%M%S}.dump"
        env = {**os.environ, "PGPASSWORD": url.password or ""}
        connection = [f"--host={url.host or 'localhost'}", f"--port={url.port or 5432}",
                      f"--username={url.username or 'postgres'}", f"--dbname={url.database}"]
        if url.query.get("sslmode"):
            env["PGSSLMODE"] = str(url.query["sslmode"])
        result = subprocess.run([dump, "--format=custom", "--no-owner", f"--file={target}", *connection],
                                env=env, capture_output=True, text=True)
        if result.returncode != 0 or not target.exists() or target.stat().st_size == 0:
            print("The backup failed, so nothing was deleted:\n" + result.stderr[-2000:])
            return 1
        print(f"Backup written: {target} ({target.stat().st_size // 1024} KB)")

    tables = [t for t in inspect(engine).get_table_names() if t not in KEEP]
    with engine.begin() as connection:
        before = {t: connection.execute(text(f'SELECT count(*) FROM "{t}"')).scalar() for t in tables}
        # The folder structure stays, but its rows point at the accounts being
        # deleted (and TRUNCATE ... CASCADE would empty it), so it is set aside
        # and put back without the "created by" link.
        folders = [dict(row) for row in connection.execute(text(
            "SELECT id, name, parent_id, is_archived, created_at, updated_at FROM document_folders ORDER BY id")).mappings()]
        names = ", ".join(f'"{t}"' for t in [*tables, "document_folders"])
        connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        pending, placed = list(folders), set()
        while pending:  # parents before their subfolders
            ready = [f for f in pending if f["parent_id"] is None or f["parent_id"] in placed]
            if not ready:
                ready = pending  # a broken parent link: keep the folders anyway
                for f in ready:
                    f["parent_id"] = None
            for folder in ready:
                connection.execute(text(
                    "INSERT INTO document_folders (id, name, parent_id, is_archived, created_by, created_at, updated_at) "
                    "VALUES (:id, :name, :parent_id, :is_archived, NULL, :created_at, :updated_at)"), folder)
                placed.add(folder["id"])
            pending = [f for f in pending if f["id"] not in placed]
        if folders:
            connection.execute(text("SELECT setval(pg_get_serial_sequence('document_folders', 'id'), "
                                    "(SELECT max(id) FROM document_folders))"))
        # Through the models, so every column default applies.
        with Session(bind=connection) as session:
            admin = User(username="admin", full_name="Administrator", role=ADMINISTRATOR, is_active=True,
                         password_hash=get_password_hash(args.admin_password))
            session.add(admin)
            session.flush()
            session.add(AuditEvent(actor_id=admin.id, actor_label="admin", action="DATA_RESET", entity_type="system",
                                   result="SUCCESS",
                                   details={"note": "All records deleted for a fresh start (scripts/reset_demo_data.py)"}))
            session.commit()  # ends the session's part; engine.begin() commits the whole reset
    removed = {t: n for t, n in before.items() if n}
    print("Deleted:", ", ".join(f"{t} {n}" for t, n in sorted(removed.items())) or "nothing")
    print("Kept:", ", ".join(sorted(KEEP)))
    print("Sign in with username 'admin' and the admin password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
