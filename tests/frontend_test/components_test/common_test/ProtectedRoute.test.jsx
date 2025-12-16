import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import ProtectedRoute from "@/components/common/ProtectedRoute";
import { useAuth } from "@/context/auth";
import { USER_ROLES } from "@/constants/UserRoles";
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
   * @param {string[]} [options.userRoles=[]] - The roles assigned to the current mocked user.
   * @param {string[]} options.requiredRoles - The roles required to access the ProtectedRoute.
   * @param {boolean} [options.loading=false] - The loading state of the authentication context.
   * @returns {Object} Result from React Testing Library's `render` function, including `container`, `debug`, etc.
   */
  const renderWithRouter = ({
    ui,
    userRoles = [],
    requiredRoles,
    loading = false,
  }) => {
    useAuth.mockReturnValue({ loading, roles: userRoles });
    return render(
      <MemoryRouter initialEntries={[ROUTE_PATHS.DASHBOARD]}>
        <Routes>
          <Route
            path={ROUTE_PATHS.DASHBOARD}
            element={
              <ProtectedRoute requiredRoles={requiredRoles}>
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
      userRoles: [],
      requiredRoles: [USER_ROLES.CC_INTERNAL],
      loading: true,
    });

    expect(container).toBeEmptyDOMElement();
  });

  test("renders access denied if user lacks mentorship role", () => {
    renderWithRouter({
      ui: <div>Personal Dashboard Page</div>,
      userRoles: [],
      requiredRoles: [USER_ROLES.MENTORSHIP],
    });

    expect(
      screen.queryByText("Personal Dashboard Page"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Access Denied Page")).toBeInTheDocument();
  });

  test("datasearch page allows admin user access", () => {
    renderWithRouter({
      ui: <div>Datasearch Page</div>,
      userRoles: [USER_ROLES.ADMIN],
      requiredRoles: [USER_ROLES.ADMIN],
    });

    expect(screen.getByText("Datasearch Page")).toBeInTheDocument();
  });

  test("datasearch page denies cc_internal and mentorship user access", () => {
    renderWithRouter({
      ui: <div>Datasearch Page</div>,
      userRoles: [USER_ROLES.MENTORSHIP, USER_ROLES.CC_INTERNAL],
      requiredRoles: [USER_ROLES.ADMIN],
    });

    expect(screen.getByText("Access Denied Page")).toBeInTheDocument();
    expect(screen.queryByText("Datasearch Page")).not.toBeInTheDocument();
  });

  test("dashboard page allows admin user access", () => {
    renderWithRouter({
      ui: <div>Dashboard Page</div>,
      userRoles: [USER_ROLES.ADMIN],
      requiredRoles: [USER_ROLES.ADMIN, USER_ROLES.CC_INTERNAL],
    });

    expect(screen.getByText("Dashboard Page")).toBeInTheDocument();
    expect(screen.queryByText("Access Denied Page")).not.toBeInTheDocument();
  });

  test("dashboard page allows cc_internal user access", () => {
    renderWithRouter({
      ui: <div>Dashboard Page</div>,
      userRoles: [USER_ROLES.CC_INTERNAL],
      requiredRoles: [USER_ROLES.ADMIN, USER_ROLES.CC_INTERNAL],
    });

    expect(screen.getByText("Dashboard Page")).toBeInTheDocument();
    expect(screen.queryByText("Access Denied Page")).not.toBeInTheDocument();
  });
});
