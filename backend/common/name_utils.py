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
  organisation. An account with no legal name is named by what the candidate
  typed into their latest application, then as ``"User <id>"``.

This module owns the second and third rules so every surface that names another person
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


def display_name_or_id(user) -> str:
    """``display_name_of``, or ``"User <id>"`` for a person with no name.

    An account created by an email-code sign-in has no first, last or preferred
    name. Wherever such a person is named in text, an empty string leaves a gap
    ("approved by ."), so this falls back to their user id instead.

    Args:
        user: A loaded ``UsersEntity``.

    Returns:
        str: The resolved display name, or ``"User <id>"`` when it is empty.
    """
    return display_name_of(user) or f"User {user.user_id}"


def _typed_name(typed_personal: dict | None) -> str:
    """The ``"first last"`` a candidate typed into an application form."""
    if not isinstance(typed_personal, dict):
        return ""
    parts = (typed_personal.get("firstName"), typed_personal.get("lastName"))
    return " ".join(p.strip() for p in parts if isinstance(p, str) and p.strip())


def candidate_legal_name(user) -> str:
    """A candidate's legal ``"first last"`` name from their account.

    Args:
        user: A ``UsersEntity``, or None when the row could not be loaded.

    Returns:
        str: ``"first last"`` trimmed, with missing parts treated as empty;
            "" when ``user`` is None or has no legal name.
    """
    if user is None:
        return ""
    return f"{user.first_name or ''} {user.last_name or ''}".strip()


def candidate_name(user, typed_personal: dict | None = None) -> str:
    """Name a candidate wherever they appear as the applicant.

    The legal name on the account comes first. An account created by an
    email-code sign-in has none, so the name the candidate typed into their
    most recent application stands in for it, and ``"User <id>"`` when they
    typed nothing either. The preferred name is never used (see the module
    docstring).

    Args:
        user: A ``UsersEntity``, or None when the row could not be loaded.
        typed_personal (dict | None): The ``personal`` block of the
            candidate's most recent application submission, if any.

    Returns:
        str: The resolved name, or "" when ``user`` is None.
    """
    if user is None:
        return ""
    return (
        candidate_legal_name(user)
        or _typed_name(typed_personal)
        or f"User {user.user_id}"
    )
