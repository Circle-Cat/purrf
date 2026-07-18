from backend.common.permissions import Permission


def _validate_complete(descriptions: dict) -> dict:
    """
    Assert every `Permission` enum member has a matching description.

    Args:
        descriptions (dict): Candidate `Permission -> str` mapping.

    Returns:
        dict: The same mapping, unchanged.

    Raises:
        ValueError: If any `Permission` member has no entry — raised at
            import time (see PERMISSION_DESCRIPTIONS below), so a permission
            added without a description fails fast instead of shipping a
            blank entry in the admin UI.
    """
    missing = set(Permission) - set(descriptions)
    if missing:
        raise ValueError(
            f"Missing permission descriptions for: {sorted(str(p) for p in missing)}"
        )
    return descriptions


# One plain-English sentence per permission, verified against actual
# authenticate()/route gates (see the design doc's Decision 7) rather than
# guessed from the name. Two permissions have no code path anywhere yet and
# are marked TODO so an admin doesn't assume granting them does something.
PERMISSION_DESCRIPTIONS: dict[Permission, str] = _validate_complete({
    Permission.SYSTEM_BACKFILL: "Run a manual data backfill job (MS Teams chat, Jira issues, Gerrit changes/projects, Google Chat history).",
    Permission.SYSTEM_BACKFILL_SCHEDULED: "Run the scheduled/automated backfill job (MS LDAP member sync, Jira project id/name sync) — used by internal service accounts.",
    Permission.SYSTEM_SYNC: "Trigger a data sync job with external systems (Jira incremental update, Calendar history pull, meeting-attendance sync, Pub/Sub consumer).",
    Permission.SYSTEM_SUBSCRIBE: "Register webhook subscriptions with Microsoft Teams/Google Chat so Purrf receives their chat event notifications.",
    Permission.INTERNAL_ACTIVITY_READ: "View internal employee activity records (MS chat, Jira, Calendar, Gerrit, Google Chat summaries).",
    Permission.DIRECTORY_MICROSOFT_LDAP_READ: "Read user directory data from Microsoft/LDAP.",
    Permission.DASHBOARD_ACTIVITY_SUMMARY_READ: "View the activity summary dashboard.",
    Permission.MENTORSHIP_ADMIN_READ: "Mentorship admin read access: the management page, per-round participant and completed-meeting counts, participant records with pair meeting logs, and cross-participant detail in meeting-log views (the basic round list needs no permission).",
    Permission.MENTORSHIP_ADMIN_WRITE: "Mentorship admin write access: create or edit mentorship rounds.",
    Permission.RECRUITING_JOB_READ: "View recruiting job postings, and access job-authoring helper lists (approvers, interview pool, owners).",
    Permission.RECRUITING_JOB_WRITE: "Create, edit, submit, close/reopen, or delete a job posting, and access job-authoring helper lists (approvers, interview pool, owners).",
    Permission.RECRUITING_JOB_APPROVE: "Approve or reject a submitted job posting, view your own review queue, and access job-authoring helper lists (approvers, interview pool, owners) — also, as an eligibility marker, appear in the 'approvers' helper list itself.",
    Permission.RECRUITING_INTERVIEW_EVALUATE: "Marks a user as eligible to be assigned as an interview evaluator on a job's pipeline stages; evaluation submission itself is enforced by a separate row-level assignee check, not directly by this permission.",
    Permission.RECRUITING_APPLICATION_ADVANCE: "Advance/reject an application's stage, reassign its interviewer, or adjust its round/sub-status; also the eligibility marker for who can own a job posting.",
    Permission.RECRUITING_APPLICATION_READ_ALL: "Org-wide override: view any job, board, application, evaluation, résumé, or activity/comment thread regardless of ownership or assignment; can also post comments — the one write action bundled into this otherwise read-only override (but does not make the holder @-mentionable).",
    Permission.RECRUITING_BLACKLIST_WRITE: "View, add to, or remove from the org-wide recruiting blacklist (one permission covers both read and write — there's no separate read grant).",
    Permission.RECRUITING_AUDIT_READ: "View the cross-posting recruiting audit page — open positions, per-job stage breakdown, and daily application trend across every posting, regardless of ownership.",
    Permission.PERMISSION_MANAGE: "View/grant/revoke user permissions, browse users and the permission catalog, view the permission-change audit log, and grant (but not revoke) super-admin status.",
    Permission.SUPER_ADMIN_REVOKE: "Revoke another user's super-admin status.",
})
