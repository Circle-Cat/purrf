import { NavLink } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { PERMISSIONS } from "@/constants/Permissions";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";

const Sidebar = () => {
  const { permissions } = useAuth();
  const flags = useFeatureFlags();

  /**
   * Checks if the user may access a page. An empty list means the item is open
   * to any authenticated user; otherwise the user needs at least one of the
   * required permissions.
   *
   * @param {Array<string>} requiredPermissions - The permissions required to access the page.
   * @returns {boolean} Whether the user may see the nav item.
   */
  const hasAccess = (requiredPermissions) => {
    return (
      requiredPermissions.length === 0 ||
      permissions.some((p) => requiredPermissions.includes(p))
    );
  };

  /**
   * Whether a nav item is on for this viewer at all.
   *
   * An item behind an unreleased feature needs both: the permission to use it
   * and the flag that says the feature exists. Reading an absent flag as false
   * is what keeps something unreleased out of the sidebar.
   *
   * @param {{permissions: Array<string>, flag?: string}} item - The nav item.
   * @returns {boolean} Whether to render it.
   */
  const isVisible = (item) =>
    hasAccess(item.permissions) && (!item.flag || Boolean(flags[item.flag]));

  const navItems = [
    {
      label: "Personal Dashboard",
      to: ROUTE_PATHS.PERSONAL_DASHBOARD,
      permissions: [],
    },
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
    {
      label: "Mentorship Management",
      to: ROUTE_PATHS.MENTORSHIP_MANAGEMENT,
      permissions: [
        PERMISSIONS.MENTORSHIP_ADMIN_READ,
        PERMISSIONS.MENTORSHIP_ADMIN_WRITE,
      ],
    },
    {
      label: "User Permissions",
      to: ROUTE_PATHS.ADMIN_USERS,
      permissions: [PERMISSIONS.PERMISSION_MANAGE],
    },
    {
      label: "Open Positions",
      to: ROUTE_PATHS.RECRUITING_JOBS_BROWSE,
      permissions: [],
    },
    {
      label: "Applications Board",
      to: ROUTE_PATHS.RECRUITING_BOARD,
      permissions: [PERMISSIONS.RECRUITING_APPLICATION_ADVANCE],
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
      label: "My Posting Reviews",
      to: ROUTE_PATHS.RECRUITING_REVIEWS,
      permissions: [PERMISSIONS.RECRUITING_JOB_APPROVE],
    },
    {
      label: "Blacklist",
      to: ROUTE_PATHS.RECRUITING_BLACKLIST,
      permissions: [PERMISSIONS.RECRUITING_BLACKLIST_WRITE],
    },
    {
      label: "Recruiting Audit",
      to: ROUTE_PATHS.RECRUITING_AUDIT,
      permissions: [PERMISSIONS.RECRUITING_AUDIT_READ],
    },
    {
      // The employee-facing leave screens are not here: whether the feature
      // applies to somebody is not a permission, and this sidebar is driven
      // entirely by permissions. Entering the calendar is a permission.
      label: "Leave Calendar",
      to: ROUTE_PATHS.LEAVE_CALENDAR_ADMIN,
      permissions: [PERMISSIONS.LEAVE_ADMIN],
      flag: FEATURE_FLAGS.LEAVE_MANAGEMENT,
    },
  ];

  return (
    <div className="fixed left-0 top-16 z-[90] flex h-[calc(100vh-64px)] w-64 shrink-0 flex-col overflow-y-auto bg-background shadow-sm transition-[width] duration-200 group-data-[env-banner=true]:top-[104px] group-data-[env-banner=true]:h-[calc(100vh-104px)] group-data-[collapsed=true]:w-0 group-data-[collapsed=true]:overflow-hidden group-data-[collapsed=true]:shadow-none">
      <nav className="p-4">
        <ul className="m-0 list-none p-0">
          {navItems.map(
            (item) =>
              isVisible(item) && (
                <li key={item.to} className="mb-[5px]">
                  <NavLink
                    to={item.to}
                    end
                    className={({ isActive }) =>
                      `flex items-center rounded-xl px-4 py-3 text-sm font-medium no-underline transition-all ${
                        isActive
                          ? "bg-primary text-primary-foreground"
                          : "text-foreground hover:bg-muted"
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ),
          )}
        </ul>
      </nav>
    </div>
  );
};

export default Sidebar;
