import { NavLink } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { USER_ROLES } from "@/constants/UserRoles";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

const Sidebar = () => {
  const { roles } = useAuth();

  /**
   * Checks if the user has at least one of the required roles to access a page or feature.
   *
   * @param {Array<string>} requiredRoles - The roles required to access the page.
   * @returns {boolean} Returns `true` if the user has at least one required role, otherwise `false`.
   */
  const hasAccess = (requiredRoles) => {
    return roles.some((role) => requiredRoles.includes(role));
  };

  const navItems = [
    {
      label: "Personal Dashboard",
      to: ROUTE_PATHS.PERSONAL_DASHBOARD,
      roles: [USER_ROLES.MENTORSHIP],
    },
    {
      label: "Dashboard",
      to: ROUTE_PATHS.DASHBOARD,
      roles: [USER_ROLES.ADMIN, USER_ROLES.CC_INTERNAL],
    },
    {
      label: "DataSearch",
      to: ROUTE_PATHS.DATASEARCH,
      roles: [USER_ROLES.ADMIN],
    },
  ];

  return (
    <div className="sidebar">
      <nav className="sidebar-nav">
        <ul>
          {navItems.map(
            (item) =>
              hasAccess(item.roles) && (
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
