import { NavLink } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { INBOX_PERMISSIONS } from "@/constants/Permissions";
import { Badge } from "@/components/ui/badge";
import { NAV_GROUPS, isNavItemVisible } from "@/components/layout/navItems";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { useInboxCount } from "@/hooks/useInboxCount";

const Sidebar = () => {
  const { permissions } = useAuth();
  const flags = useFeatureFlags();
  const { count: inboxCount } = useInboxCount(
    permissions.some((p) => INBOX_PERMISSIONS.includes(p)),
  );

  const groups = NAV_GROUPS.map((group) => ({
    key: group.key,
    items: group.items.filter((item) =>
      isNavItemVisible(item, { permissions, flags }),
    ),
  })).filter((group) => group.items.length > 0);

  return (
    <div className="fixed left-0 top-16 z-[90] flex h-[calc(100vh-64px)] w-64 shrink-0 flex-col overflow-y-auto bg-background shadow-sm transition-[width] duration-200 group-data-[env-banner=true]:top-[104px] group-data-[env-banner=true]:h-[calc(100vh-104px)] group-data-[collapsed=true]:w-0 group-data-[collapsed=true]:overflow-hidden group-data-[collapsed=true]:shadow-none">
      <nav className="p-4">
        <ul className="m-0 list-none p-0">
          {groups.map((group) => (
            <li key={group.key} data-nav-group={group.key}>
              <ul className="m-0 list-none p-0">
                {group.items.map((item) => (
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
                      {item.badgeKey === "inbox" && inboxCount > 0 && (
                        <Badge className="ml-auto rounded-full px-2 py-0 text-xs">
                          {inboxCount}
                        </Badge>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
};

export default Sidebar;
