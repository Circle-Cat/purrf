import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import ProtectedRoute from "@/components/common/ProtectedRoute";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

// ── Page mocks (routing test only — heavy page internals are irrelevant) ───────
vi.mock("@/pages/RecruitingAdmin", () => ({
  default: () => (
    <div data-testid="recruiting-admin-page">Recruiting Admin</div>
  ),
}));
vi.mock("@/pages/RecruitingApply", () => ({
  default: () => (
    <div data-testid="recruiting-apply-page">Recruiting Apply</div>
  ),
}));
vi.mock("@/pages/RecruitingScreening", () => ({
  default: () => (
    <div data-testid="recruiting-screening-page">Recruiting Screening</div>
  ),
}));

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

import RecruitingAdmin from "@/pages/RecruitingAdmin";
import RecruitingApply from "@/pages/RecruitingApply";
import RecruitingScreening from "@/pages/RecruitingScreening";

/**
 * Renders a minimal route table that mirrors how App.jsx declares the three
 * recruiting routes, starting at `initialPath`.
 *
 * @param {string} initialPath - The route to start the router at.
 * @param {string[]} permissions - Permissions granted to the mock user.
 */
const renderRoutingTable = (initialPath, permissions = []) => {
  useAuth.mockReturnValue({ loading: false, permissions });
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        {/* Permission-gated routes */}
        <Route
          path={ROUTE_PATHS.RECRUITING_ADMIN}
          element={
            <ProtectedRoute
              requiredPermissions={[PERMISSIONS.RECRUITING_JOB_READ]}
            >
              <RecruitingAdmin />
            </ProtectedRoute>
          }
        />
        <Route
          path={ROUTE_PATHS.RECRUITING_SCREENING}
          element={
            <ProtectedRoute
              requiredPermissions={[PERMISSIONS.RECRUITING_APPLICATION_READ]}
            >
              <RecruitingScreening />
            </ProtectedRoute>
          }
        />
        {/* Authenticated-but-unpermissioned route */}
        <Route
          path={ROUTE_PATHS.RECRUITING_APPLY}
          element={<RecruitingApply />}
        />
        {/* Access-denied sentinel */}
        <Route
          path={ROUTE_PATHS.ACCESS_DENIED}
          element={<div data-testid="access-denied-page">Access Denied</div>}
        />
      </Routes>
    </MemoryRouter>,
  );
};

describe("Recruiting routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── RecruitingAdmin ─────────────────────────────────────────────────────────

  test("/recruiting/admin mounts RecruitingAdmin for user with RECRUITING_JOB_READ", () => {
    renderRoutingTable(ROUTE_PATHS.RECRUITING_ADMIN, [
      PERMISSIONS.RECRUITING_JOB_READ,
    ]);
    expect(screen.getByTestId("recruiting-admin-page")).toBeInTheDocument();
    expect(screen.queryByTestId("access-denied-page")).not.toBeInTheDocument();
  });

  test("/recruiting/admin redirects to access-denied when user lacks RECRUITING_JOB_READ", () => {
    renderRoutingTable(ROUTE_PATHS.RECRUITING_ADMIN, []);
    expect(screen.getByTestId("access-denied-page")).toBeInTheDocument();
    expect(
      screen.queryByTestId("recruiting-admin-page"),
    ).not.toBeInTheDocument();
  });

  // ── RecruitingScreening ─────────────────────────────────────────────────────

  test("/recruiting/screening/:jobId mounts RecruitingScreening for user with RECRUITING_APPLICATION_READ", () => {
    renderRoutingTable("/recruiting/screening/42", [
      PERMISSIONS.RECRUITING_APPLICATION_READ,
    ]);
    expect(screen.getByTestId("recruiting-screening-page")).toBeInTheDocument();
    expect(screen.queryByTestId("access-denied-page")).not.toBeInTheDocument();
  });

  test("/recruiting/screening/:jobId redirects to access-denied when user lacks RECRUITING_APPLICATION_READ", () => {
    renderRoutingTable("/recruiting/screening/42", []);
    expect(screen.getByTestId("access-denied-page")).toBeInTheDocument();
    expect(
      screen.queryByTestId("recruiting-screening-page"),
    ).not.toBeInTheDocument();
  });

  // ── RecruitingApply (open to any authenticated user) ───────────────────────

  test("/recruiting/apply/:jobId mounts RecruitingApply for user with no recruiting permissions", () => {
    renderRoutingTable("/recruiting/apply/7", []);
    expect(screen.getByTestId("recruiting-apply-page")).toBeInTheDocument();
    expect(screen.queryByTestId("access-denied-page")).not.toBeInTheDocument();
  });

  test("/recruiting/apply/:jobId mounts RecruitingApply for user with RECRUITING_JOB_READ", () => {
    renderRoutingTable("/recruiting/apply/7", [
      PERMISSIONS.RECRUITING_JOB_READ,
    ]);
    expect(screen.getByTestId("recruiting-apply-page")).toBeInTheDocument();
  });
});
