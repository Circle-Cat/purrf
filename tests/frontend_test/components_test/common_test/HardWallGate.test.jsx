import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

import HardWallGate from "@/components/common/HardWallGate";
import { useAuth } from "@/context/auth";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

describe("HardWallGate Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  /**
   * Render HardWallGate wrapping a small route tree, with mocked auth.
   *
   * @param {Object} options
   * @param {boolean} [options.hasVerifiedEmail=false] - Whether the user holds a confirmed email.
   * @param {boolean} [options.loading=false] - The auth context loading state.
   * @param {boolean} [options.accessDenied=false] - Whether the auth pull came back 403.
   * @param {string} [options.accessDeniedMessage=""] - The denial reason from the 403 response.
   * @param {string} options.initialPath - The path the router starts at.
   * @returns {Object} React Testing Library render result.
   */
  const renderGate = ({
    hasVerifiedEmail = false,
    loading = false,
    accessDenied = false,
    accessDeniedMessage = "",
    authError = false,
    sessionExpired = false,
    initialPath,
  }) => {
    useAuth.mockReturnValue({
      loading,
      hasVerifiedEmail,
      accessDenied,
      accessDeniedMessage,
      authError,
      sessionExpired,
      refreshAuth: vi.fn(),
    });
    return render(
      <MemoryRouter initialEntries={[initialPath]}>
        <HardWallGate>
          <Routes>
            <Route
              path={ROUTE_PATHS.VERIFY_REQUIRED}
              element={<div>Verify Wall</div>}
            />
            <Route
              path={ROUTE_PATHS.PROFILE}
              element={<div>Profile Page</div>}
            />
            <Route
              path={ROUTE_PATHS.DASHBOARD}
              element={<div>Dashboard Page</div>}
            />
          </Routes>
        </HardWallGate>
      </MemoryRouter>,
    );
  };

  test("renders nothing while loading is true", () => {
    const { container } = renderGate({
      loading: true,
      initialPath: ROUTE_PATHS.DASHBOARD,
    });

    expect(container).toBeEmptyDOMElement();
  });

  test("redirects an unverified user away from a protected page to the wall", () => {
    renderGate({
      hasVerifiedEmail: false,
      initialPath: ROUTE_PATHS.DASHBOARD,
    });

    expect(screen.getByText("Verify Wall")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard Page")).not.toBeInTheDocument();
  });

  test("lets an unverified user stay on the wall page", () => {
    renderGate({
      hasVerifiedEmail: false,
      initialPath: ROUTE_PATHS.VERIFY_REQUIRED,
    });

    expect(screen.getByText("Verify Wall")).toBeInTheDocument();
  });

  test("redirects a verified user off the wall to the profile page", () => {
    renderGate({
      hasVerifiedEmail: true,
      initialPath: ROUTE_PATHS.VERIFY_REQUIRED,
    });

    expect(screen.getByText("Profile Page")).toBeInTheDocument();
    expect(screen.queryByText("Verify Wall")).not.toBeInTheDocument();
  });

  test("lets a verified user reach a protected page", () => {
    renderGate({
      hasVerifiedEmail: true,
      initialPath: ROUTE_PATHS.DASHBOARD,
    });

    expect(screen.getByText("Dashboard Page")).toBeInTheDocument();
    expect(screen.queryByText("Verify Wall")).not.toBeInTheDocument();
  });

  test("shows the 403 page with the denial message when access is denied", () => {
    const message =
      "Your account has been deactivated. Contact an administrator to restore access.";
    renderGate({
      accessDenied: true,
      accessDeniedMessage: message,
      initialPath: ROUTE_PATHS.DASHBOARD,
    });

    expect(screen.getByText("403 Forbidden")).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.queryByText("Dashboard Page")).not.toBeInTheDocument();
    expect(screen.queryByText("Verify Wall")).not.toBeInTheDocument();
  });

  test("shows the 403 page instead of bouncing an unverified denied user to the wall", () => {
    renderGate({
      hasVerifiedEmail: false,
      accessDenied: true,
      accessDeniedMessage: "",
      initialPath: ROUTE_PATHS.DASHBOARD,
    });

    expect(screen.getByText("403 Forbidden")).toBeInTheDocument();
    expect(screen.queryByText("Verify Wall")).not.toBeInTheDocument();
  });

  test("shows the 403 page even when sitting on the verify wall path", () => {
    renderGate({
      accessDenied: true,
      accessDeniedMessage: "Access revoked.",
      initialPath: ROUTE_PATHS.VERIFY_REQUIRED,
    });

    expect(screen.getByText("403 Forbidden")).toBeInTheDocument();
    expect(screen.getByText("Access revoked.")).toBeInTheDocument();
    expect(screen.queryByText("Verify Wall")).not.toBeInTheDocument();
  });

  test("shows a retry screen (not the verify wall) on a transient auth load failure", () => {
    renderGate({
      hasVerifiedEmail: false,
      authError: true,
      initialPath: ROUTE_PATHS.DASHBOARD,
    });

    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(screen.queryByText("Verify Wall")).not.toBeInTheDocument();
    expect(screen.queryByText("Dashboard Page")).not.toBeInTheDocument();
  });

  test("shows a session-expired screen (not the verify wall) on a 401", () => {
    renderGate({
      hasVerifiedEmail: false,
      authError: true,
      sessionExpired: true,
      initialPath: ROUTE_PATHS.DASHBOARD,
    });

    expect(screen.getByText(/session has expired/i)).toBeInTheDocument();
    expect(screen.queryByText("Verify Wall")).not.toBeInTheDocument();
  });

  test("prefers the 403 page over the auth-error screen", () => {
    renderGate({
      accessDenied: true,
      accessDeniedMessage: "Access revoked.",
      authError: true,
      initialPath: ROUTE_PATHS.DASHBOARD,
    });

    expect(screen.getByText("403 Forbidden")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /retry/i }),
    ).not.toBeInTheDocument();
  });
});
