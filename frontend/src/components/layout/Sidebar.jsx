import { NavLink } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

const Sidebar = () => {
  const { permissions } = useAuth();

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
      permissions: [PERMISSIONS.MENTORSHIP_MANAGEMENT_READ],
    },
  ];

  return (
    <div className="sidebar">
      <nav className="sidebar-nav">
        <ul>
          {navItems.map(
            (item) =>
              hasAccess(item.permissions) && (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end
                    className={({ isActive }) =>
                      isActive ? "active-link" : ""
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
