"""Shared internal-employee lifecycle hook for corp sign-ins joining an
EXISTING account (bridge link, in-account verify, or trusted-assertion
routing): grant the internal-employee permission bundle and promote the
corp address to the primary contact. Lives outside both services so the
logic exists once."""

from backend.common.permissions import INTERNAL_EMPLOYEE_PERMISSIONS


async def absorb_internal_identity(
    session,
    user_id: int,
    email: str,
    *,
    user_permissions_repository,
    user_emails_repository,
    users_repository,
    logger,
) -> None:
    """
    Mirror the first-login lifecycle hook when a corp sign-in joins an
    EXISTING account (bridge link, in-account verify, or trusted-assertion
    routing): grant the internal-employee permission bundle and promote the
    corp address to the primary contact.

    Without this, an employee who linked their corp sign-in into a
    pre-existing external account would be INTERNAL without the baseline
    permissions a first-login hire gets, with a personal address still
    receiving account mail. Grants are diffed against the user's active
    permissions first (``grant()`` never dedups), so re-verifying is
    idempotent; the promotion is skipped when the corp address is already
    the primary or (defensively) not confirmed. Flushes only — the caller
    owns the transaction boundary.

    Args:
        session (AsyncSession): The active async database session.
        user_id (int): The account the corp sign-in was linked into.
        email (str): The corp address (normalized) that was just verified.
        users_repository (UsersRepository): Repository handling UsersEntity,
            used to set the is_internal flag.
    """
    # Persist the internal-employee state (idempotent — set_internal no-ops
    # when already True), the sole classification signal in the row-less model.
    await users_repository.set_internal(session, user_id)

    active = await user_permissions_repository.get_active_permission_names(
        session, user_id
    )
    held = set(active)
    missing = sorted(
        (p for p in INTERNAL_EMPLOYEE_PERMISSIONS if str(p) not in held), key=str
    )
    if missing:
        await user_permissions_repository.grant(
            session=session,
            user_id=user_id,
            permission_names=missing,
            granted_source="system_internal",
        )
        logger.info(
            "[internal_lifecycle] granted internal bundle to user_id=%s "
            "on corp sign-in link",
            user_id,
        )

    row = await user_emails_repository.get_by_user_and_email(session, user_id, email)
    if row is not None and row.otp_confirmed and not row.is_primary:
        await user_emails_repository.set_primary(session, user_id, row.email_id)
        logger.info(
            "[internal_lifecycle] promoted corp email to primary for user_id=%s",
            user_id,
        )
