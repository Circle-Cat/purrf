#!/usr/bin/env python3
"""Readiness check for retiring the legacy ``users.primary_email`` column.

The column can only be dropped once every active user has a confirmed PRIMARY
contact email in ``user_emails`` (an ``is_primary=True`` row). That row is
created organically as users hit the ``/verify-required`` hard wall and verify
on login (``EmailManagementService._confirm_email`` promotes the first confirmed
address to primary when the user has none). Until then their primary lives only
in ``users.primary_email``, so dropping the column would leave them with no
notification target.

This script reports the remaining gap. When "active users missing a primary
user_emails row" reaches 0 (or only dormant accounts that will never log in
again remain), it is safe to cut the ~76 read sites over to ``user_emails`` and
drop the column.

Run against PROD (or a prod-synced DB):

    DATABASE_URL="postgresql://USER:PW@HOST/DB?sslmode=require" \
        python3 tools/primary_email_readiness.py

A SQLAlchemy-style async URL (``postgresql+asyncpg://...?ssl=require``) is
accepted too and normalized to psycopg2 form. The script is read-only.
"""

import os
import sys

import psycopg2


def _normalize_url(url: str) -> str:
    """Accept the project's async DATABASE_URL and coerce it to psycopg2 form."""
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("ssl=require", "sslmode=require")
    return url


_QUERY = """
WITH active AS (
    SELECT user_id, primary_email FROM users WHERE is_active
),
missing_primary AS (
    SELECT a.user_id, a.primary_email
    FROM active a
    WHERE NOT EXISTS (
        SELECT 1 FROM user_emails ue
        WHERE ue.user_id = a.user_id AND ue.is_primary
    )
)
SELECT
    (SELECT count(*) FROM active) AS active_users,
    (SELECT count(*) FROM missing_primary) AS missing_primary_row,
    (SELECT count(*) FROM missing_primary m
       WHERE EXISTS (
         SELECT 1 FROM user_emails ue
         WHERE ue.user_id = m.user_id
           AND lower(ue.email) = lower(m.primary_email)
       )) AS legacy_email_present_unconfirmed
"""


def main() -> int:
    raw = os.getenv("DATABASE_URL")
    if not raw:
        print("ERROR: set DATABASE_URL (point it at prod or a prod-synced DB).")
        return 2

    conn = psycopg2.connect(_normalize_url(raw))
    try:
        cur = conn.cursor()
        cur.execute(_QUERY)
        active, missing, legacy_present = cur.fetchone()
    finally:
        conn.close()

    pct = (missing / active * 100) if active else 0
    print("=== users.primary_email retirement readiness ===")
    print(f"  active users ................................. {active}")
    print(f"  ACTIVE USERS MISSING a primary user_emails row {missing}  ({pct:.0f}%)")
    print(f"    of those, legacy primary_email present but   ")
    print(f"    unconfirmed (will self-heal on verify) ..... {legacy_present}")
    print()
    if missing == 0:
        print("READY: every active user has a confirmed primary in user_emails.")
        print("Safe to cut reads to user_emails and drop users.primary_email.")
        return 0
    print(f"NOT READY: {missing} active user(s) still rely on users.primary_email.")
    print("They get a primary user_emails row only after passing the verify hard")
    print("wall on next login. Re-run later, or backfill-confirm the stragglers.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
