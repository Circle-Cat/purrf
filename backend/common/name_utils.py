"""Helpers for rendering user names consistently across the app.

The product rule is:

* When a user views their **own** name, or in internal/admin audit views, the
  ``first_name``, ``last_name`` and ``preferred_name`` fields are shown
  separately and verbatim.
* When a user views **someone else's** name (e.g. a mentorship partner), the
  preferred name takes priority, falling back to the full ``"first last"`` name.

This module owns that second rule so every partner-facing surface resolves the
display name the same way.
"""


def partner_display_name(
    *,
    first_name: str | None,
    last_name: str | None,
    preferred_name: str | None,
) -> str:
    """Resolve the name to show for a mentorship partner (a non-self person).

    The preferred name wins when present; otherwise the full ``"first last"``
    name is used. Empty or whitespace-only values are treated as absent, and the
    result is trimmed of surrounding whitespace.

    Args:
        first_name (str | None): The partner's legal first name.
        last_name (str | None): The partner's legal last name.
        preferred_name (str | None): The partner's chosen preferred name, if any.

    Returns:
        str: The preferred name, or the full ``"first last"`` name as a fallback.
    """
    if preferred_name and preferred_name.strip():
        return preferred_name.strip()
    return f"{first_name or ''} {last_name or ''}".strip()
