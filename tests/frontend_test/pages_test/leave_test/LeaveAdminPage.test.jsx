import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import LeaveAdminPage from "@/pages/Leave/AdminPage";
import * as api from "@/api/leaveApi";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";

vi.mock("@/api/leaveApi");
vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

const envelope = (data) => ({ success: true, message: "ok", data });

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/leave/admin"]}>
      <Routes>
        <Route path="/leave/admin" element={<LeaveAdminPage />} />
        <Route path="/dashboard/me" element={<p>Personal dashboard</p>} />
      </Routes>
    </MemoryRouter>,
  );

describe("LeaveAdminPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.LEAVE_MANAGEMENT]: true });
    api.getLeaveBalances.mockResolvedValue(
      envelope({
        people: [],
        excluded: {
          left: [],
          noHireDate: [],
          unreadable: [],
          unresolved: [],
          notInternal: [],
        },
        profileCount: 0,
      }),
    );
    api.getLeaveHolidayYears.mockResolvedValue(
      envelope({ years: [2026], currentYear: 2026, nextYear: 2027 }),
    );
    api.getLeaveHolidays.mockResolvedValue(
      envelope({ year: 2026, totalDays: 0, segments: [] }),
    );
  });

  it("sends somebody away when the feature is switched off", () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.LEAVE_MANAGEMENT]: false,
    });

    renderPage();

    expect(screen.getByText("Personal dashboard")).toBeInTheDocument();
    expect(api.getLeaveBalances).not.toHaveBeenCalled();
  });

  it("keeps both administrative jobs on one page", async () => {
    // Two sidebar entries invited reading "Leave Balances" as somebody's own
    // balance, which is a different screen and belongs on the dashboard.
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Leave administration")).toBeInTheDocument(),
    );
    expect(screen.getByRole("tab", { name: "Balances" })).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Yearly setup" }),
    ).toBeInTheDocument();
  });

  it("opens on the balances, which is what an admin comes to read", async () => {
    renderPage();

    await waitFor(() => expect(api.getLeaveBalances).toHaveBeenCalled());
  });
});
