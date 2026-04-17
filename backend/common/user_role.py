from enum import Enum


class UserRole(str, Enum):
    """
    Roles are assigned from Cloudflare Access (extn.purrf_role claim) or inferred from token type.

    Cloudflare roles (set in Cloudflare Access per user):
      superAdmin      - full access; expands to INFRA_ADMIN + MANAGER + MENTORSHIP_ADMIN at login
      infraAdmin      - system maintenance: backfill, consumers, notification subscriptions
      manager         - read internal member activity data (chat, Jira, calendar, Gerrit)
      mentorshipAdmin - manage mentorship rounds and view detailed meeting data

    Auto-assigned roles (inferred at login, not set in Cloudflare):
      ccInternal          - CircleCat employees (@u.circlecat.org)
      mentorship          - all Cloudflare-authenticated users
      contactGoogleChat   - external Google OAuth users (@google.com)
      cronRunner          - Google service accounts running cron jobs

    To add a new role: add the enum value here, update SUPER_ADMIN_ROLES if superAdmin
    should include it, then annotate endpoints with @authenticate(roles=[UserRole.<NEW_ROLE>]).
    """

    SUPER_ADMIN = "superAdmin"
    INFRA_ADMIN = "infraAdmin"
    MANAGER = "manager"
    MENTORSHIP_ADMIN = "mentorshipAdmin"
    CC_INTERNAL = "ccInternal"
    MENTORSHIP = "mentorship"
    CONTACT_GOOGLE_CHAT = "contactGoogleChat"
    CRON_RUNNER = "cronRunner"


# All roles granted to superAdmin. Add new roles here when they should be included.
SUPER_ADMIN_ROLES: list["UserRole"] = [
    UserRole.INFRA_ADMIN,
    UserRole.MANAGER,
    UserRole.MENTORSHIP_ADMIN,
    UserRole.CC_INTERNAL,
    UserRole.CONTACT_GOOGLE_CHAT,
    UserRole.CRON_RUNNER,
]
