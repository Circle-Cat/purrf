from enum import Enum


class ApprovalStatus(str, Enum):
    SIGNED_UP = "signed_up"
    MATCHED = "matched"
    UN_MATCHED = "un_matched"
    REJECTED = "rejected"


class CommunicationMethod(str, Enum):
    EMAIL = "email"
    GOOGLE_CHAT = "google_chat"


class Degree(str, Enum):
    ASSOCIATE = "Associate"
    BACHELOR = "Bachelor"
    MASTER = "Master"
    DOCTORATE = "Doctorate"
    PROFESSIONAL = "Professional"


class UserTimezone(Enum):
    AMERICA_LOS_ANGELES = "America/Los_Angeles"
    AMERICA_NEW_YORK = "America/New_York"
    ASIA_SHANGHAI = "Asia/Shanghai"
    AMERICA_DENVER = "America/Denver"


class PairStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MentorActionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class MenteeActionStatus(str, Enum):
    PENDING = "pending"
    TIME_PROPOSED = "time_proposed"
    CONFIRMED = "confirmed"


class ParticipantRole(Enum):
    MENTOR = "mentor"
    MENTEE = "mentee"


class TrainingCategory(str, Enum):
    MENTORSHIP_MENTEE_ONBOARDING = "mentorship_mentee_onboarding"
    MENTORSHIP_MENTOR_ONBOARDING = "mentorship_mentor_onboarding"
    RESIDENCY_PROGRAM_ONBOARDING = "residency_program_onboarding"
    CORPORATE_CULTURE_COURSE = "corporate_culture_course"


class TrainingStatus(str, Enum):
    TO_DO = "to_do"
    IN_PROGRESS = "in_progress"
    DONE = "done"
