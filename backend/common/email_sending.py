"""Whether this environment sends email at all.

Test and staging run on a copy of prod's people, so left alone they email real
colleagues -- and they share the mailbox's daily sending quota with prod.
``EMAIL_SENDING_ENABLED`` switches off every email Purrf sends through Gmail:
notifications, recruiting and participant emails, Inbox replies. Reading the
mailbox carries on. Prod leaves it unset, and unset means on, so a missing
variable can never silence prod.

Kit broadcasts do not go through Gmail; the ``mentorship-kit-email`` flag gates
those.
"""

import os

from backend.common.environment_constants import EMAIL_SENDING_ENABLED

# Spellings that switch email off. Anything else, including unset, leaves it on.
_OFF_VALUES = frozenset({"false", "0", "no", "off"})

SENDING_OFF_MESSAGE = "Email is switched off in this environment."


class EmailSendingDisabledError(ValueError, LookupError):
    """An email was about to go out while sending is switched off.

    A ``ValueError`` so a send a person started answers 400 with this message,
    and a ``LookupError`` so notification delivery marks it failed for good
    rather than retrying it until the switch is turned back on.
    """


def email_sending_enabled() -> bool:
    """Whether the environment says email may be sent.

    Returns:
        False when ``EMAIL_SENDING_ENABLED`` is false, 0, no or off (any case);
        True otherwise, including when it is unset.
    """
    value = os.getenv(EMAIL_SENDING_ENABLED) or ""
    return value.strip().lower() not in _OFF_VALUES
