import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "@/components/layout/Sidebar";
import { useAuth } from "@/context/auth";
import { FlagsContext } from "@/context/flags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { PERMISSIONS } from "@/constants/Permissions";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));
vi.mock("@/api/inboxApi", () => ({
  getInboxCount: vi.fn(() => Promise.resolve({ data: { needsReply: 0 } })),
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
  const renderSidebar = (
    permissions = [],
    initialPath = ROUTE_PATHS.ROOT,
    flags = {},
  ) => {
    useAuth.mockReturnValue({ permissions });
    return render(
      <FlagsContext.Provider
        value={{ flags, setFlags: () => {}, ready: true, setReady: () => {} }}
      >
        <MemoryRouter initialEntries={[initialPath]}>
          <Sidebar />
        </MemoryRouter>
      </FlagsContext.Provider>,
    );
  };

  const groupWrapper = (key) =>
    document.querySelector(`[data-tour="nav-group-${key}"]`);

  const linkLabels = (element) =>
    Array.from(element.querySelectorAll("a")).map((a) => a.textContent);

  test("renders only Personal Dashboard for a user with no permissions", () => {
    renderSidebar([]);

    // Personal Dashboard is open to any authenticated user (no permission gate).
    expect(screen.getByText("Personal Dashboard")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    expect(screen.queryByText("DataSearch")).not.toBeInTheDocument();
  });

  test("renders Open Positions for a user with no permissions and links to the jobs browse page", () => {
    renderSidebar([]);

    const link = screen.getByText("Open Positions");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute(
      "href",
      ROUTE_PATHS.RECRUITING_JOBS_BROWSE,
    );
  });

  test("lists every entry in group order for a user who sees everything", () => {
    renderSidebar(Object.values(PERMISSIONS), ROUTE_PATHS.ROOT, {
      [FEATURE_FLAGS.LEAVE_MANAGEMENT]: true,
    });

    expect(linkLabels(document.querySelector("nav"))).toEqual([
      "Personal Dashboard",
      "Open Positions",
      "Inbox",
      "Applications Board",
      "My Interview Evaluations",
      "Job Postings",
      "Recruiting Audit",
      "Mentorship Management",
      "Dashboard",
      "DataSearch",
      "Accounts",
      "User Permissions",
      "Leave Administration",
      "Training Administration",
    ]);
    expect(
      Array.from(document.querySelectorAll("[data-tour]")).map((el) =>
        el.getAttribute("data-tour"),
      ),
    ).toEqual([
      "nav-group-me",
      "nav-group-apply",
      "nav-group-recruiting",
      "nav-group-mentorship",
      "nav-group-activity",
      "nav-group-admin",
    ]);
  });

  test("wraps only the groups that have a visible entry, around just those entries", () => {
    renderSidebar([PERMISSIONS.RECRUITING_AUDIT_READ, PERMISSIONS.USER_ADMIN]);

    expect(linkLabels(groupWrapper("me"))).toEqual(["Personal Dashboard"]);
    expect(linkLabels(groupWrapper("apply"))).toEqual(["Open Positions"]);
    expect(linkLabels(groupWrapper("recruiting"))).toEqual([
      "Recruiting Audit",
    ]);
    expect(linkLabels(groupWrapper("admin"))).toEqual(["Accounts"]);
    expect(groupWrapper("mentorship")).toBeNull();
    expect(groupWrapper("activity")).toBeNull();
  });

  test("leaves out a group whose only entries are behind an off flag", () => {
    renderSidebar([PERMISSIONS.LEAVE_ADMIN, PERMISSIONS.MENTORSHIP_ADMIN_READ]);

    expect(groupWrapper("admin")).toBeNull();
    expect(linkLabels(groupWrapper("mentorship"))).toEqual([
      "Mentorship Management",
    ]);
  });

  test("no longer marks Open Positions with its own tour anchor", () => {
    renderSidebar([]);

    expect(
      document.querySelector('[data-tour="nav-open-positions"]'),
    ).toBeNull();
    expect(screen.getByText("Open Positions").closest("a")).not.toHaveAttribute(
      "data-tour",
    );
  });

  test("hides Applications Board for a user with no permissions", () => {
    renderSidebar([]);

    expect(screen.queryByText("Applications Board")).not.toBeInTheDocument();
  });

  test("renders Applications Board for a user with recruiting.application.advance and links to the board page", () => {
    renderSidebar([PERMISSIONS.RECRUITING_APPLICATION_ADVANCE]);

    const link = screen.getByText("Applications Board");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute(
      "href",
      ROUTE_PATHS.RECRUITING_BOARD,
    );
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

  test("renders Mentorship Management for a user with admin-read permission", () => {
    renderSidebar([PERMISSIONS.MENTORSHIP_ADMIN_READ]);

    expect(screen.getByText("Mentorship Management")).toBeInTheDocument();
    expect(screen.getByText("Personal Dashboard")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    expect(screen.queryByText("DataSearch")).not.toBeInTheDocument();
  });

  test("shows Mentorship Management for a write-only admin", () => {
    renderSidebar([PERMISSIONS.MENTORSHIP_ADMIN_WRITE]);
    expect(screen.getByText("Mentorship Management")).toBeInTheDocument();
  });

  test("does not render Mentorship Management without admin-read permission", () => {
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

    expect(dashBoardLink).toHaveAttribute("aria-current", "page");
    expect(dataSearchLink).toBeNull();
  });

  test("renders User Permissions for a user with permission.manage", () => {
    renderSidebar([PERMISSIONS.PERMISSION_MANAGE]);
    expect(screen.getByText("User Permissions")).toBeInTheDocument();
  });

  test("does not render User Permissions without permission.manage", () => {
    renderSidebar([PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ]);
    expect(screen.queryByText("User Permissions")).not.toBeInTheDocument();
  });

  test("renders Accounts for a user with user.admin permission", () => {
    renderSidebar([PERMISSIONS.USER_ADMIN]);
    const link = screen.getByText("Accounts");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute(
      "href",
      ROUTE_PATHS.ADMIN_ACCOUNTS,
    );
  });

  test("does not render Accounts without user.admin", () => {
    renderSidebar([PERMISSIONS.RECRUITING_JOB_APPROVE]);
    expect(screen.queryByText("Accounts")).not.toBeInTheDocument();
  });

  test("no longer offers a Blacklist entry to anyone", () => {
    renderSidebar([
      PERMISSIONS.USER_ADMIN,
      PERMISSIONS.RECRUITING_JOB_APPROVE,
      PERMISSIONS.RECRUITING_APPLICATION_ADVANCE,
    ]);
    expect(screen.queryByText("Blacklist")).not.toBeInTheDocument();
  });

  test("renders Recruiting Audit for a user with recruiting.audit.read permission", () => {
    renderSidebar([PERMISSIONS.RECRUITING_AUDIT_READ]);
    const link = screen.getByText("Recruiting Audit");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute(
      "href",
      ROUTE_PATHS.RECRUITING_AUDIT,
    );
  });

  test("does not render Recruiting Audit without recruiting.audit.read permission", () => {
    renderSidebar([PERMISSIONS.RECRUITING_JOB_APPROVE]);
    expect(screen.queryByText("Recruiting Audit")).not.toBeInTheDocument();
  });

  test("renders Training Administration for a user with training.admin.read permission", () => {
    renderSidebar([PERMISSIONS.TRAINING_ADMIN_READ]);
    const link = screen.getByText("Training Administration");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute(
      "href",
      ROUTE_PATHS.ADMIN_TRAINING,
    );
  });

  test("does not render Training Administration without training.admin.read permission", () => {
    renderSidebar([PERMISSIONS.RECRUITING_JOB_APPROVE]);
    expect(
      screen.queryByText("Training Administration"),
    ).not.toBeInTheDocument();
  });
});
