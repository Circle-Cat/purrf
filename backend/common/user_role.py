from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    CC_INTERNAL = "cc_internal"
    MENTORSHIP = "mentorship"
    CONTACT_GOOGLE_CHAT = "contactGoogleChat"
    CRON_RUNNER = "cronRunner"
