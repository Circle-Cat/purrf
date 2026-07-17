"""Backfill user_identities and user_emails from existing users

Data migration for the identity/email split introduced by dee5e8b0c892 and the
permission work in f2a9c7b41d3e. The old schema stored a single Auth0 sub and
the email directly on ``users``; this revision populates one row per user in the
new tables so existing accounts keep working after the cut-over.

Per user:

* user_identities -- one row.
    - subject_identifier: if the legacy sub looks like ``auth0|...`` we strip the
      ``auth0|`` connection prefix and keep the remainder as the real sub (e.g.
      ``auth0|email|abc`` -> ``email|abc``), which is the form the new auth layer
      presents, so ``find_user_by_sub`` matches directly on next login. Any other
      sub gets a ``manual|<user_id>`` placeholder; on first real login
      ``find_swappable_by_email`` (which only matches ``manual|%`` rows) re-links
      it by email_claim and overwrites the placeholder with the real sub.
    - identity_type: ``internal`` when the primary email is on a company domain
      (``@circlecat.org`` / ``@u.circlecat.org``, mirroring is_company_email),
      otherwise ``external``.
    - email_claim: the lower-cased primary email (the swap path matches on the
      lower-cased address).

* user_emails -- one row for the primary email, plus one per alternative email.
    - Primary: a legacy ``auth0|email|...`` sub means the address was already
      proven via the Auth0 passwordless one-time-code round-trip, so the row is
      seeded otp_confirmed=True and is_primary=True. Every other sub is seeded
      otp_confirmed=False, and therefore is_primary=False to satisfy the
      ``primary_must_be_confirmed`` CHECK; those users confirm the address (and
      promote it to primary) through the hard-wall verify flow on next login.
    - Alternatives: every distinct entry of ``users.alternative_emails`` (a
      legacy text array dropped later in the chain by f3d9a2b6c8e1) becomes an
      unverified backup row — otp_confirmed=False, is_primary=False — matching
      what POST /auth/emails/add writes today. No sign-in is auto-linked off
      these claims; the user unlocks one by verifying it from inside the
      account. Blank entries and duplicates of the primary are skipped.

* user_permissions -- the INTERNAL_EMPLOYEE_PERMISSIONS bundle for every active
  internal user, mirroring the first-login lifecycle hook so migrated employees
  and brand-new hires end up with the same baseline. Names are literals here
  (migrations must not import app code); keep in sync with
  ``backend/common/permissions.py``. All other permissions stay manual grants,
  and users.is_super_admin is left at its default of false.

Revision ID: b7e3c1d05a92
Revises: f2a9c7b41d3e
Create Date: 2026-06-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7e3c1d05a92"
down_revision: Union[str, Sequence[str], None] = "f2a9c7b41d3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill the new identity/email rows from existing users."""
    # One identity row per user. 'auth0|_%' (prefix plus at least one more char)
    # guards against an empty suffix; substring(... from 7) drops the 6-char
    # 'auth0|' prefix.
    op.execute(
        sa.text(
            """
            INSERT INTO user_identities
                (user_id, subject_identifier, identity_type, email_claim, linked_at)
            SELECT
                u.user_id,
                CASE
                    WHEN u.subject_identifier LIKE 'auth0|_%'
                        THEN substring(u.subject_identifier FROM 7)
                    ELSE 'manual|' || u.user_id::text
                END,
                CASE
                    WHEN lower(u.primary_email) LIKE '%@circlecat.org'
                      OR lower(u.primary_email) LIKE '%@u.circlecat.org'
                        THEN 'internal'
                    ELSE 'external'
                END,
                lower(u.primary_email),
                now()
            FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM user_identities ui WHERE ui.user_id = u.user_id
            )
            """
        )
    )

    # One primary-email row per user. otp_confirmed and is_primary are the same
    # predicate so the primary_must_be_confirmed CHECK always holds.
    op.execute(
        sa.text(
            """
            INSERT INTO user_emails
                (user_id, email, otp_confirmed, is_primary, added_at)
            SELECT
                u.user_id,
                lower(u.primary_email),
                (u.subject_identifier LIKE 'auth0|email|%'),
                (u.subject_identifier LIKE 'auth0|email|%'),
                now()
            FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM user_emails ue
                WHERE ue.user_id = u.user_id
                  AND ue.email = lower(u.primary_email)
            )
            """
        )
    )

    # One unverified backup row per distinct alternative email. unnest of a
    # NULL array yields no rows, so users without alternatives are skipped
    # for free. DISTINCT collapses duplicates within one user's array after
    # normalization; the NOT EXISTS guard keeps the statement idempotent and
    # skips addresses already present (including the primary row above, but
    # the explicit primary comparison also covers users whose primary insert
    # was skipped by its own guard).
    op.execute(
        sa.text(
            """
            INSERT INTO user_emails
                (user_id, email, otp_confirmed, is_primary, added_at)
            SELECT DISTINCT
                u.user_id,
                lower(trim(alt.email)),
                FALSE,
                FALSE,
                now()
            FROM users u
            CROSS JOIN LATERAL unnest(u.alternative_emails) AS alt(email)
            WHERE alt.email IS NOT NULL
              AND trim(alt.email) <> ''
              AND lower(trim(alt.email)) <> lower(u.primary_email)
              AND NOT EXISTS (
                  SELECT 1 FROM user_emails ue
                  WHERE ue.user_id = u.user_id
                    AND ue.email = lower(trim(alt.email))
              )
            """
        )
    )

    # The internal-employee baseline bundle, mirroring the first-login
    # lifecycle hook in UserIdentityService (granted_source='system_internal',
    # granted_by NULL = system). Idempotent: users already holding an
    # unrevoked row for a bundle permission are skipped, so re-running (or a
    # user graced by the first-login hook between deploys) never duplicates.
    op.execute(
        sa.text(
            """
            INSERT INTO user_permissions
                (user_id, permission_name, granted_source, granted_by)
            SELECT u.user_id, p.permission_name, 'system_internal', NULL
            FROM users u
            CROSS JOIN (VALUES
                ('directory.microsoft_ldap.read'),
                ('dashboard.activity_summary.read')
            ) AS p(permission_name)
            WHERE u.is_active
              AND EXISTS (
                  SELECT 1 FROM user_identities ui
                  WHERE ui.user_id = u.user_id
                    AND ui.identity_type = 'internal'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM user_permissions up
                  WHERE up.user_id = u.user_id
                    AND up.permission_name = p.permission_name
                    AND up.revoked_timestamp IS NULL
              )
            """
        )
    )


def downgrade() -> None:
    """Empty the backfilled tables.

    This revision is the initial population of user_identities and user_emails,
    which dee5e8b0c892 created empty; reverting it clears them. There is no
    per-row marker distinguishing backfilled rows from later writes (the
    first-login hook stamps the same 'system_internal' source), so this is
    only a clean inverse at/around the deploy boundary.
    """
    op.execute(
        sa.text("DELETE FROM user_permissions WHERE granted_source = 'system_internal'")
    )
    op.execute(sa.text("DELETE FROM user_emails"))
    op.execute(sa.text("DELETE FROM user_identities"))
