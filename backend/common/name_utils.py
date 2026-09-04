"""Helpers for rendering user names consistently across the app.

The product rule is:

* When a user views their **own** name, or in internal/admin audit views, the
  ``first_name``, ``last_name`` and ``preferred_name`` fields are shown
  separately and verbatim.
* When a user views **someone else's** name, the preferred name takes priority,
  falling back to the full ``"first last"`` name.
* A **candidate** in the recruiting module is named by their legal
  ``"first last"`` name wherever they appear as the applicant -- board cards,
  application detail, notifications about them, calendar invitations and the
  emails they receive. Their own preferred name does not override it, because
  those surfaces are records of, or correspondence with, a person outside the
  organisation.

This module owns the second rule so every surface that names another person
resolves it the same way.

The first rule needs no helper on this side -- the fields travel separately and
each view renders them as it sees fit. Where a view has room for one cell only
(the "By" column of an audit row, say), the frontend's ``legalName`` drops the
preferred name rather than substituting it: dropping a nickname is a small loss,
substituting it defeats the point of an identity-confirming view.
"""


def user_display_name(
    *,
    first_name: str | None,
    last_name: str | None,
    preferred_name: str | None,
) -> str:
    """Resolve the name to show for a person other than the viewer.

    The preferred name wins when present; otherwise the full ``"first last"``
    name is used. Empty or whitespace-only values are treated as absent, and the
    result is trimmed of surrounding whitespace.

    Args:
        first_name (str | None): The person's legal first name.
        last_name (str | None): The person's legal last name.
        preferred_name (str | None): The person's chosen preferred name, if any.

    Returns:
        str: The preferred name, or the full ``"first last"`` name as a fallback.
    """
    if preferred_name and preferred_name.strip():
        return preferred_name.strip()
    return f"{first_name or ''} {last_name or ''}".strip()


def display_name_of(user) -> str:
    """``user_display_name`` for a row that already carries the three names.

    Args:
        user: Anything exposing ``first_name``, ``last_name`` and
            ``preferred_name`` -- in practice a ``UsersEntity``. ``None`` when
            the row could not be loaded.

    Returns:
        str: The resolved display name, or "" when ``user`` is None.
    """
    if user is None:
        return ""
    return user_display_name(
        first_name=user.first_name,
        last_name=user.last_name,
        preferred_name=user.preferred_name,
    )
