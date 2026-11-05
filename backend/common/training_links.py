"""Where a seed training category's course lives when we do not host it."""

import os

from backend.common.environment_constants import (
    MENTORSHIP_MENTEE_ONBOARDING_LINK,
    MENTORSHIP_MENTOR_ONBOARDING_LINK,
)
from backend.common.mentorship_enums import TrainingCategory

# Only the two mentorship onboarding courses were ever hosted elsewhere.
_CATEGORY_LINK_ENV_VAR = {
    TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING: MENTORSHIP_MENTOR_ONBOARDING_LINK,
    TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING: MENTORSHIP_MENTEE_ONBOARDING_LINK,
}


def external_link_for(category: TrainingCategory | None) -> str | None:
    """The externally hosted course for a category, or None.

    Derived, never stored: the value is an environment variable, so a copy on
    a row goes stale the moment an environment points somewhere else.

    Args:
        category (TrainingCategory | None): The course's category, if it has
            one. A course created from the admin page has none.

    Returns:
        str | None: The URL, or None for a category with no link configured.
    """
    if category is None:
        return None
    env_var = _CATEGORY_LINK_ENV_VAR.get(category)
    return os.getenv(env_var) if env_var else None
