"""revoke recruiting.blacklist.write grants

Revision ID: 57aca149ba67
Revises: 24cf994c2693
Create Date: 2026-09-05

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "57aca149ba67"
down_revision: Union[str, Sequence[str], None] = "24cf994c2693"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Revoke every outstanding grant of the retired permission.

    permission_name is a plain String(64) validated in the application, not
    by the database, so removing the enum member leaves live rows naming a
    permission that resolves to nothing -- readable in the audit view, matched
    by no gate, and impossible to revoke through the UI once the name is gone
    from the catalog. Revoking them here keeps the grant history honest: the
    rows stay, stamped with the moment the permission was retired.

    revoked_by stays NULL, which the column allows: nobody revoked these,
    the permission did.
    """
    op.execute(
        """
        UPDATE user_permissions
           SET revoked_timestamp = now()
         WHERE permission_name = 'recruiting.blacklist.write'
           AND revoked_timestamp IS NULL
        """
    )


def downgrade() -> None:
    """Deliberately not reinstated.

    The permission no longer exists in code, so an un-revoked row would
    resolve to nothing. Downgrading the schema does not bring the enum member
    back, and a row naming a permission the catalog has never heard of is
    exactly what the upgrade exists to prevent.
    """
