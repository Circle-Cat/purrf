import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import LeaveAdminPage from "@/pages/Leave/AdminPage";
import * as api from "@/api/leaveApi";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { useLeaveBalances } from "@/pages/Leave/hooks/useLeaveBalances";
import { FlagsContext } from "@/context/flags";

vi.mock("@/api/leaveApi");
vi.mock("@/pages/Leave/hooks/useLeaveBalances");
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

    vi.mocked(useLeaveBalances).mockReturnValue({
      people: [
        {
          userId: 42,
          name: "Alice Smith",
          ldap: "asmith",
          annualHours: 160,
          balanceHours: "40.00",
          level: "L3",
          problems: [],
        },
      ],
      excluded: {},
      profileCount: 1,
      isLoading: false,
      loadError: false,
      isSaving: false,
      saveError: null,
      lastResult: null,
      clearResult: vi.fn(),
      load: vi.fn(),
      adjust: vi.fn(),
    });

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

    api.getLeaveLedger.mockResolvedValue(
      envelope({
        entries: [],
        totalEntries: 0,
      }),
    );
  });

  it("does not send somebody away while flags are still loading", () => {
    useFeatureFlags.mockReturnValue({});

    render(
      <FlagsContext.Provider
        value={{ flags: {}, setFlags: () => {}, ready: false }}
      >
        <MemoryRouter initialEntries={["/leave/admin"]}>
          <Routes>
            <Route path="/leave/admin" element={<LeaveAdminPage />} />
            <Route path="/dashboard/me" element={<p>Personal dashboard</p>} />
          </Routes>
        </MemoryRouter>
      </FlagsContext.Provider>,
    );

    expect(screen.queryByText("Personal dashboard")).not.toBeInTheDocument();
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
    expect(screen.getByRole("tab", { name: "Ledger" })).toBeInTheDocument();
  });

  it("opens on the balances, which is what an admin comes to read", async () => {
    renderPage();

    await waitFor(() => expect(useLeaveBalances).toHaveBeenCalled());
    expect(screen.getByText("Alice Smith")).toBeInTheDocument();
  });

  it("switches to Ledger tab and passes userId when 'View history' is clicked in Balances", async () => {
    api.getLeaveLedger.mockResolvedValueOnce(
      envelope({
        entries: [
          {
            leaveLedgerId: 101,
            userId: 42,
            name: "Alice Smith",
            ldap: "asmith",
            hours: "40.00",
            entryType: "weekly_accrual",
            effectiveDate: "2026-01-01",
          },
        ],
        totalEntries: 1,
      }),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Alice Smith")).toBeInTheDocument();
    });

    const viewHistoryButton = screen.getByRole("button", {
      name: "View history",
    });
    fireEvent.click(viewHistoryButton);

    await waitFor(() => {
      expect(api.getLeaveLedger).toHaveBeenCalledWith({
        userId: 42,
        page: 1,
        pageSize: 50,
      });
    });

    await waitFor(() => {
      const select = screen.getByLabelText(/Filter by Person/i);
      expect(select).toHaveValue("42");
    });
  });
});
