"""Resolve candidates' names, reading their typed name only when needed.

``name_utils.candidate_name`` decides the name; this module fetches what it
needs to decide. The typed name lives in the candidate's latest application
submission, so it is read only for candidates whose account has no legal
name, and for a whole page of them in one query.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.name_utils import candidate_legal_name, candidate_name


async def candidate_names(
    session: AsyncSession, application_submission_repository, users
) -> dict[int, str]:
    """Name every candidate in ``users``.

    Args:
        session (AsyncSession): Active database async session.
        application_submission_repository (ApplicationSubmissionRepository):
            Reads the typed names.
        users (Iterable[UsersEntity]): The candidates to name.

    Returns:
        dict[int, str]: Each candidate's name keyed by user id.
    """
    users = list(users)
    nameless_ids = sorted({u.user_id for u in users if not candidate_legal_name(u)})
    typed = (
        await application_submission_repository.get_latest_personal_by_user_ids(
            session, nameless_ids
        )
        if nameless_ids
        else {}
    )
    return {u.user_id: candidate_name(u, typed.get(u.user_id)) for u in users}


async def candidate_name_of(
    session: AsyncSession, application_submission_repository, user
) -> str:
    """``candidate_names`` for one candidate.

    Args:
        session (AsyncSession): Active database async session.
        application_submission_repository (ApplicationSubmissionRepository):
            Reads the typed name.
        user (UsersEntity | None): The candidate, or None when the row could
            not be loaded.

    Returns:
        str: The candidate's name, or "" when ``user`` is None.
    """
    if user is None:
        return ""
    names = await candidate_names(session, application_submission_repository, [user])
    return names[user.user_id]
