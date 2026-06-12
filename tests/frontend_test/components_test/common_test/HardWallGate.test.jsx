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
   * @param {string} options.initialPath - The path the router starts at.
   * @returns {Object} React Testing Library render result.
   */
  const renderGate = ({
    hasVerifiedEmail = false,
    loading = false,
    initialPath,
  }) => {
    useAuth.mockReturnValue({ loading, hasVerifiedEmail });
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
});
