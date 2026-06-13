import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import ProtectedRoute from "@/components/common/ProtectedRoute";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

describe("ProtectedRoute Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  /**
   * A helper function to render a component with mocked routing and authentication context.
   * It mocks `useAuth` and wraps the target UI in a `MemoryRouter` with required routes.
   *
   * @param {Object} options - Configuration for rendering.
   * @param {React.ReactNode} options.ui - The component or JSX to render inside the ProtectedRoute.
   * @param {string[]} [options.userPermissions=[]] - The permissions assigned to the current mocked user.
   * @param {string[]} options.requiredPermissions - The permissions required to access the ProtectedRoute.
   * @param {boolean} [options.loading=false] - The loading state of the authentication context.
   * @returns {Object} Result from React Testing Library's `render` function, including `container`, `debug`, etc.
   */
  const renderWithRouter = ({
    ui,
    userPermissions = [],
    requiredPermissions,
    loading = false,
  }) => {
    useAuth.mockReturnValue({ loading, permissions: userPermissions });
    return render(
      <MemoryRouter initialEntries={[ROUTE_PATHS.DASHBOARD]}>
        <Routes>
          <Route
            path={ROUTE_PATHS.DASHBOARD}
            element={
              <ProtectedRoute requiredPermissions={requiredPermissions}>
                {ui}
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTE_PATHS.ACCESS_DENIED}
            element={<div>Access Denied Page</div>}
          />
        </Routes>
      </MemoryRouter>,
    );
  };

  test("renders nothing while loading is true", () => {
    const { container } = renderWithRouter({
      ui: <div>Dashboard Page</div>,
      userPermissions: [],
      requiredPermissions: [PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ],
      loading: true,
    });

    expect(container).toBeEmptyDOMElement();
  });

  test("renders access denied if user lacks the required permission", () => {
    renderWithRouter({
      ui: <div>Datasearch Page</div>,
      userPermissions: [],
      requiredPermissions: [PERMISSIONS.INTERNAL_ACTIVITY_READ],
    });

    expect(screen.queryByText("Datasearch Page")).not.toBeInTheDocument();
    expect(screen.getByText("Access Denied Page")).toBeInTheDocument();
  });

  test("datasearch page allows user with internal_activity.read", () => {
    renderWithRouter({
      ui: <div>Datasearch Page</div>,
      userPermissions: [PERMISSIONS.INTERNAL_ACTIVITY_READ],
      requiredPermissions: [PERMISSIONS.INTERNAL_ACTIVITY_READ],
    });

    expect(screen.getByText("Datasearch Page")).toBeInTheDocument();
  });

  test("datasearch page denies user with only dashboard summary read", () => {
    renderWithRouter({
      ui: <div>Datasearch Page</div>,
      userPermissions: [PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ],
      requiredPermissions: [PERMISSIONS.INTERNAL_ACTIVITY_READ],
    });

    expect(screen.getByText("Access Denied Page")).toBeInTheDocument();
    expect(screen.queryByText("Datasearch Page")).not.toBeInTheDocument();
  });

  test("dashboard page allows user with dashboard summary read", () => {
    renderWithRouter({
      ui: <div>Dashboard Page</div>,
      userPermissions: [PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ],
      requiredPermissions: [PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ],
    });

    expect(screen.getByText("Dashboard Page")).toBeInTheDocument();
    expect(screen.queryByText("Access Denied Page")).not.toBeInTheDocument();
  });
});
