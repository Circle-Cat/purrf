import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "@/components/layout/Sidebar";
import { useAuth } from "@/context/auth";
import { USER_ROLES } from "@/constants/UserRoles";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

describe("Sidebar Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  /**
   * Helper function to render Sidebar with mocked auth and router context.
   *
   * @param {string[]} roles - The roles assigned to the current user.
   * @param {string} [initialPath="/"] - The current active route path (for testing active states).
   */
  const renderSidebar = (roles = [], initialPath = ROUTE_PATHS.ROOT) => {
    useAuth.mockReturnValue({ roles });
    return render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Sidebar />
      </MemoryRouter>,
    );
  };

  test("renders nothing if user has no roles", () => {
    renderSidebar([]);

    const listItems = screen.queryAllByRole("listitem");

    expect(listItems).toHaveLength(0);
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    expect(screen.queryByText("DataSearch")).not.toBeInTheDocument();
    expect(screen.queryByText("Personal Dashboard")).not.toBeInTheDocument();
  });

  test("renders all links for admin user", () => {
    renderSidebar([USER_ROLES.ADMIN, USER_ROLES.MENTORSHIP]);

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("DataSearch")).toBeInTheDocument();
    expect(screen.getByText("Personal Dashboard")).toBeInTheDocument();
  });

  test("renders all links except DataSearch for cc_internal user", () => {
    renderSidebar([USER_ROLES.CC_INTERNAL, USER_ROLES.MENTORSHIP]);

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.queryByText("DataSearch")).not.toBeInTheDocument();
    expect(screen.getByText("Personal Dashboard")).toBeInTheDocument();
  });

  test("renders PersonalDashboard link for mentorship user", () => {
    renderSidebar([USER_ROLES.MENTORSHIP]);

    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    expect(screen.queryByText("DataSearch")).not.toBeInTheDocument();
    expect(screen.getByText("Personal Dashboard")).toBeInTheDocument();
  });

  test("applies active class to the current route link", () => {
    renderSidebar(
      [USER_ROLES.CC_INTERNAL, USER_ROLES.MENTORSHIP],
      ROUTE_PATHS.DASHBOARD,
    );

    const dashBoardLink = screen.getByText("Dashboard");
    const dataSearchLink = screen.queryByText("DataSearch");

    expect(dashBoardLink).toHaveClass("active-link");
    expect(dataSearchLink).toBeNull();
  });
});
