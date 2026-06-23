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

  test("renders Mentorship Management for a user with management-read permission", () => {
    renderSidebar([PERMISSIONS.MENTORSHIP_MANAGEMENT_READ]);

    expect(screen.getByText("Mentorship Management")).toBeInTheDocument();
    expect(screen.getByText("Personal Dashboard")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    expect(screen.queryByText("DataSearch")).not.toBeInTheDocument();
  });

  test("does not render Mentorship Management without management-read permission", () => {
    renderSidebar([
      PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ,
      PERMISSIONS.INTERNAL_ACTIVITY_READ,
    ]);

    expect(screen.queryByText("Mentorship Management")).not.toBeInTheDocument();
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

  // ── Recruiting nav items ────────────────────────────────────────────────────

  test("renders Recruiting Admin for a user with RECRUITING_JOB_READ", () => {
    renderSidebar([PERMISSIONS.RECRUITING_JOB_READ]);

    expect(screen.getByText("Recruiting Admin")).toBeInTheDocument();
    expect(screen.queryByText("Recruiting Screening")).not.toBeInTheDocument();
  });

  test("renders Recruiting Screening for a user with RECRUITING_APPLICATION_READ", () => {
    renderSidebar([PERMISSIONS.RECRUITING_APPLICATION_READ]);

    expect(screen.getByText("Recruiting Screening")).toBeInTheDocument();
    expect(screen.queryByText("Recruiting Admin")).not.toBeInTheDocument();
  });

  test("renders both Recruiting Admin and Recruiting Screening for a user with both recruiting permissions", () => {
    renderSidebar([
      PERMISSIONS.RECRUITING_JOB_READ,
      PERMISSIONS.RECRUITING_APPLICATION_READ,
    ]);

    expect(screen.getByText("Recruiting Admin")).toBeInTheDocument();
    expect(screen.getByText("Recruiting Screening")).toBeInTheDocument();
  });

  test("does not render Recruiting Admin or Recruiting Screening for a user with no recruiting permissions", () => {
    renderSidebar([PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ]);

    expect(screen.queryByText("Recruiting Admin")).not.toBeInTheDocument();
    expect(screen.queryByText("Recruiting Screening")).not.toBeInTheDocument();
  });
});
