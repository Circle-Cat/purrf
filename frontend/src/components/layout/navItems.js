import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { INBOX_PERMISSIONS, PERMISSIONS } from "@/constants/Permissions";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * The sidebar's entries, grouped in display order.
 *
 * An item's `permissions` is any-of; an empty list means every signed-in
 * user. `flag` names a feature flag that must also be on.
 *
 * @type {Array<{
 *   key: string,
 *   items: Array<{
 *     label: string,
 *     to: string,
 *     permissions: string[],
 *     flag?: string,
 *     badgeKey?: string,
 *   }>,
 * }>}
 */
export const NAV_GROUPS = [
  {
    key: "me",
    items: [
      {
        label: "Personal Dashboard",
        to: ROUTE_PATHS.PERSONAL_DASHBOARD,
        permissions: [],
      },
    ],
  },
  {
    key: "apply",
    items: [
      {
        label: "Open Positions",
        to: ROUTE_PATHS.RECRUITING_JOBS_BROWSE,
        permissions: [],
      },
    ],
  },
  {
    key: "recruiting",
    items: [
      {
        label: "Inbox",
        to: ROUTE_PATHS.INBOX,
        permissions: INBOX_PERMISSIONS,
        badgeKey: "inbox",
      },
      {
        label: "Applications Board",
        to: ROUTE_PATHS.RECRUITING_BOARD,
        permissions: [
          PERMISSIONS.RECRUITING_APPLICATION_ADVANCE,
          PERMISSIONS.RECRUITING_APPLICATION_READ_ALL,
        ],
      },
      {
        label: "My Interview Evaluations",
        to: ROUTE_PATHS.RECRUITING_MY_EVALUATIONS,
        permissions: [PERMISSIONS.RECRUITING_INTERVIEW_EVALUATE],
      },
      {
        label: "Job Postings",
        to: ROUTE_PATHS.RECRUITING_POSTINGS,
        permissions: [
          PERMISSIONS.RECRUITING_JOB_WRITE,
          PERMISSIONS.RECRUITING_JOB_READ,
          PERMISSIONS.RECRUITING_JOB_APPROVE,
        ],
      },
      {
        label: "Recruiting Audit",
        to: ROUTE_PATHS.RECRUITING_AUDIT,
        permissions: [PERMISSIONS.RECRUITING_AUDIT_READ],
      },
    ],
  },
  {
    key: "mentorship",
    items: [
      {
        label: "Mentorship Management",
        to: ROUTE_PATHS.MENTORSHIP_MANAGEMENT,
        permissions: [
          PERMISSIONS.MENTORSHIP_ADMIN_READ,
          PERMISSIONS.MENTORSHIP_ADMIN_WRITE,
        ],
      },
    ],
  },
  {
    key: "activity",
    items: [
      {
        label: "Dashboard",
        to: ROUTE_PATHS.DASHBOARD,
        permissions: [PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ],
      },
      {
        label: "DataSearch",
        to: ROUTE_PATHS.DATASEARCH,
        permissions: [PERMISSIONS.INTERNAL_ACTIVITY_READ],
      },
    ],
  },
  {
    key: "admin",
    items: [
      {
        label: "Accounts",
        to: ROUTE_PATHS.ADMIN_ACCOUNTS,
        permissions: [PERMISSIONS.USER_ADMIN],
      },
      {
        label: "User Permissions",
        to: ROUTE_PATHS.ADMIN_USERS,
        permissions: [PERMISSIONS.PERMISSION_MANAGE],
      },
      {
        // Only the administrative side. Whether leave applies to somebody is
        // not a permission and this sidebar is driven entirely by
        // permissions, so the employee-facing screens live on the dashboard
        // instead.
        label: "Leave Administration",
        to: ROUTE_PATHS.LEAVE_ADMIN,
        permissions: [PERMISSIONS.LEAVE_ADMIN],
        flag: FEATURE_FLAGS.LEAVE_MANAGEMENT,
      },
      {
        // Same shape as Leave Administration above: this is the admin-only
        // catalogue, not the learner-facing course page, which has no nav
        // entry of its own -- it's reached from a training assignment.
        label: "Training Administration",
        to: ROUTE_PATHS.ADMIN_TRAINING,
        permissions: [PERMISSIONS.TRAINING_ADMIN_READ],
      },
    ],
  },
];

/**
 * Whether a nav item is on for this viewer. An item behind an unreleased
 * feature needs both the permission and the flag; an absent flag reads as
 * off, which keeps unreleased entries out of the sidebar.
 *
 * @param {{permissions: string[], flag?: string}} item - The nav item.
 * @param {{permissions: string[], flags: Record<string, any>}} viewer - The
 *   viewer's permissions and feature flag values.
 * @returns {boolean} Whether to show it.
 */
export const isNavItemVisible = (item, { permissions, flags }) =>
  (item.permissions.length === 0 ||
    permissions.some((p) => item.permissions.includes(p))) &&
  (!item.flag || Boolean(flags[item.flag]));
