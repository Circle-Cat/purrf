import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "@/components/layout/Sidebar";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
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
   * @param {string[]} permissions - The permissions assigned to the current user.
   * @param {string} [initialPath="/"] - The current active route path (for testing active states).
   */
  const renderSidebar = (permissions = [], initialPath = ROUTE_PATHS.ROOT) => {
    useAuth.mockReturnValue({ permissions });
    return render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Sidebar />
      </MemoryRouter>,
    );
  };

  test("renders only Personal Dashboard for a user with no permissions", () => {
    renderSidebar([]);

    // Personal Dashboard is open to any authenticated user (no permission gate).
    expect(screen.getByText("Personal Dashboard")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    expect(screen.queryByText("DataSearch")).not.toBeInTheDocument();
  });

  test("renders all links for a user with both internal permissions", () => {
    renderSidebar([
      PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ,
      PERMISSIONS.INTERNAL_ACTIVITY_READ,
    ]);

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("DataSearch")).toBeInTheDocument();
    expect(screen.getByText("Personal Dashboard")).toBeInTheDocument();
  });

  test("renders Dashboard and Personal Dashboard but not DataSearch for a dashboard-only user", () => {
    renderSidebar([PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ]);

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.queryByText("DataSearch")).not.toBeInTheDocument();
    expect(screen.getByText("Personal Dashboard")).toBeInTheDocument();
  });

  test("applies active class to the current route link", () => {
    renderSidebar(
      [PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ],
      ROUTE_PATHS.DASHBOARD,
    );

    const dashBoardLink = screen.getByText("Dashboard");
    const dataSearchLink = screen.queryByText("DataSearch");

    expect(dashBoardLink).toHaveClass("active-link");
    expect(dataSearchLink).toBeNull();
  });
});
