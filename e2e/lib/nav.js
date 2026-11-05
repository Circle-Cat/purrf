const INBOX = [
  "mentorship.admin.write",
  "recruiting.application.advance",
  "inquiries.manage",
];

/**
 * The sidebar as a user should see it: who gets each entry and where it
 * leads. Written independently of Sidebar.jsx on purpose, so a change there
 * that hides or adds an entry shows up as a failure.
 * `flagged` entries also sit behind a LaunchDarkly flag and may be absent.
 */
export const NAV = [
  { label: "Personal Dashboard", path: "/dashboard/me", anyOf: [] },
  {
    label: "Dashboard",
    path: "/dashboard",
    anyOf: ["dashboard.activity_summary.read"],
  },
  {
    label: "DataSearch",
    path: "/datasearch",
    anyOf: ["internal_activity.read"],
  },
  {
    label: "Mentorship Management",
    path: "/mentorship-management",
    anyOf: ["mentorship.admin.read", "mentorship.admin.write"],
  },
  { label: "Accounts", path: "/admin/accounts", anyOf: ["user.admin"] },
  {
    label: "User Permissions",
    path: "/admin/users",
    anyOf: ["permission.manage"],
  },
  { label: "Open Positions", path: "/recruiting/jobs", anyOf: [] },
  { label: "Inbox", path: "/inbox", anyOf: INBOX },
  {
    label: "Applications Board",
    path: "/recruiting/board",
    anyOf: [
      "recruiting.application.advance",
      "recruiting.application.read.all",
    ],
  },
  {
    label: "My Interview Evaluations",
    path: "/recruiting/my-evaluations",
    anyOf: ["recruiting.interview.evaluate"],
  },
  {
    label: "Job Postings",
    path: "/recruiting/postings",
    anyOf: [
      "recruiting.job.write",
      "recruiting.job.read",
      "recruiting.job.approve",
    ],
  },
  {
    label: "Recruiting Audit",
    path: "/recruiting/audit",
    anyOf: ["recruiting.audit.read"],
  },
  {
    label: "Leave Administration",
    path: "/leave/admin",
    anyOf: ["leave.admin"],
    flagged: true,
  },
  {
    label: "Training Administration",
    path: "/admin/training",
    anyOf: ["training.admin.read"],
  },
];

export const canSee = (item, permissions) =>
  item.anyOf.length === 0 || item.anyOf.some((p) => permissions.includes(p));
