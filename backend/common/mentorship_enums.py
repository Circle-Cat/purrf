from enum import Enum


class CommunicationMethod(str, Enum):
    EMAIL = "email"
    GOOGLE_CHAT = "google_chat"


class UserTimezone(Enum):
    AMERICA_LOS_ANGELES = "America/Los_Angeles"
    AMERICA_NEW_YORK = "America/New_York"
    ASIA_SHANGHAI = "Asia/Shanghai"
    AMERICA_DENVER = "America/Denver"


class TrainingCategory(str, Enum):
    MENTORSHIP_MENTEE_ONBOARDING = "mentorship_mentee_onboarding"
    MENTORSHIP_MENTOR_ONBOARDING = "mentorship_mentor_onboarding"
    RESIDENCY_PROGRAM_ONBOARDING = "residency_program_onboarding"
    CORPORATE_CULTURE_COURSE = "corporate_culture_course"


class TrainingStatus(str, Enum):
    TO_DO = "to_do"
    IN_PROGRESS = "in_progress"
    DONE = "done"
