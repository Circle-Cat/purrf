from enum import Enum


class UserTimezone(Enum):
    America_Los_Angeles = "America/Los_Angeles"
    America_New_York = "America/New_York"
    Asia_Shanghai = "Asia/Shanghai"
    America_Denver = "America/Denver"


class TrainingCategory(str, Enum):
    MENTORSHIP_MENTEE_ONBOARDING = "mentorship_mentee_onboarding"
    MENTORSHIP_MENTOR_ONBOARDING = "mentorship_mentor_onboarding"
    RESIDENCY_PROGRAM_ONBOARDING = "residency_program_onboarding"
    CORPORATE_CULTURE_COURSE = "corporate_culture_course"


class TrainingStatus(str, Enum):
    TO_DO = "to_do"
    IN_PROGRESS = "in_progress"
    DONE = "done"
