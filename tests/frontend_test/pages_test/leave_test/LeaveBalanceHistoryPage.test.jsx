import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

import BalanceHistoryPage from "@/pages/Leave/BalanceHistoryPage";
import * as api from "@/api/leaveApi";
import { useLeaveStanding } from "@/pages/Leave/hooks/useLeaveStanding";
import { useMyLeaveLedger } from "@/pages/Leave/hooks/useMyLeaveLedger";
import { useLeaveEnabled } from "@/pages/Leave/hooks/useLeaveEnabled";
import {
  formatBusinessDate,
  LEAVE_CALENDAR_ZONE_LABEL,
} from "@/pages/Leave/utils/leaveDates";

vi.mock("@/api/leaveApi");
vi.mock("@/pages/Leave/hooks/useLeaveStanding");
vi.mock("@/pages/Leave/hooks/useMyLeaveLedger");
vi.mock("@/pages/Leave/hooks/useLeaveEnabled");

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<BalanceHistoryPage />} />
        <Route path="/dashboard/me" element={<div>Redirected</div>} />
      </Routes>
    </MemoryRouter>,
  );

describe("BalanceHistoryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useLeaveEnabled).mockReturnValue(true);
    vi.mocked(useMyLeaveLedger).mockReturnValue({
      data: null,
      isLoading: false,
      loadError: null,
      load: vi.fn(),
    });

    vi.mocked(useLeaveStanding).mockReturnValue({
      isCovered: true,
      isLoading: false,
    });
  });

  it("shows an empty-state sentence when entries are empty", async () => {
    vi.mocked(useMyLeaveLedger).mockReturnValue({
      data: {
        balanceHours: "0.00",
        entries: [],
      },
      isLoading: false,
      loadError: null,
      load: vi.fn(),
    });

    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText("No balance history entries found."),
      ).toBeInTheDocument(),
    );

    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("displays negative balance without error styling", async () => {
    vi.mocked(useMyLeaveLedger).mockReturnValue({
      data: {
        balanceHours: "-16.00",
        entries: [
          {
            id: "1",
            effectiveDate: "2026-05-06",
            entryType: "leave_deduction",
            hours: "-16.00",
            note: null,
          },
        ],
      },
      isLoading: false,
      loadError: null,
      load: vi.fn(),
    });

    renderPage();

    const allMatches = screen.getAllByText("-16.00 h");
    const rowHours = allMatches.find((el) =>
      el.className.includes("text-rose-600"),
    );
    expect(rowHours).toBeInTheDocument();
    expect(rowHours.className).toMatch(/text-rose-600/);

    const footerBalance = allMatches.find((el) =>
      el.className.includes("font-mono"),
    );
    expect(footerBalance).toBeInTheDocument();
    expect(footerBalance.className).toMatch(/font-mono/);
  });

  it("renders English labels for all 6 entry types and raw value for unrecognised type", async () => {
    vi.mocked(useMyLeaveLedger).mockReturnValue({
      data: {
        balanceHours: "33.54",
        entries: [
          {
            id: "1",
            effectiveDate: "2026-01-01",
            entryType: "weekly_accrual",
            hours: "1.54",
            note: null,
          },
          {
            id: "2",
            effectiveDate: "2026-01-02",
            entryType: "leave_deduction",
            hours: "-8.00",
            note: null,
          },
          {
            id: "3",
            effectiveDate: "2026-01-03",
            entryType: "level_change",
            hours: "0.00",
            note: null,
          },
          {
            id: "4",
            effectiveDate: "2026-01-04",
            entryType: "manual_adjustment",
            hours: "40.00",
            note: null,
          },
          {
            id: "5",
            effectiveDate: "2026-01-05",
            entryType: "exchange_credit",
            hours: "8.00",
            note: null,
          },
          {
            id: "6",
            effectiveDate: "2026-01-06",
            entryType: "carryover_forfeit",
            hours: "-4.00",
            note: null,
          },
          {
            id: "7",
            effectiveDate: "2026-01-07",
            entryType: "custom_future_type",
            hours: "0.00",
            note: null,
          },
        ],
      },
      isLoading: false,
      loadError: null,
      load: vi.fn(),
    });

    renderPage();

    expect(await screen.findByText("Weekly accrual")).toBeInTheDocument();
    expect(screen.getByText("Leave taken")).toBeInTheDocument();
    expect(screen.getByText("Level change")).toBeInTheDocument();
    expect(screen.getByText("Adjustment by administrator")).toBeInTheDocument();
    expect(screen.getByText("Holiday worked")).toBeInTheDocument();
    expect(screen.getByText("Carry-over cap")).toBeInTheDocument();
    expect(screen.getByText("custom_future_type")).toBeInTheDocument();
  });

  it("renders the timezone once in the footer using LEAVE_CALENDAR_ZONE_LABEL and formats dates", async () => {
    vi.mocked(useMyLeaveLedger).mockReturnValue({
      data: {
        balanceHours: "10.00",
        entries: [
          {
            id: "1",
            effectiveDate: "2026-10-01",
            entryType: "weekly_accrual",
            hours: "10.00",
            note: "Test entry",
          },
        ],
      },
      isLoading: false,
      loadError: null,
      load: vi.fn(),
    });

    renderPage();

    expect(
      screen.getByText(formatBusinessDate("2026-10-01")),
    ).toBeInTheDocument();

    expect(screen.getByText(LEAVE_CALENDAR_ZONE_LABEL)).toBeInTheDocument();
  });

  it("renders 'Leave isn't tracked for your account.' and no balance when isCovered is false", async () => {
    useLeaveStanding.mockReturnValue({ isCovered: false, isLoading: false });

    renderPage();

    expect(
      screen.getByText("Leave isn't tracked for your account."),
    ).toBeInTheDocument();

    expect(screen.queryByText(/0\.00 h/)).not.toBeInTheDocument();
    expect(screen.queryByText("Balance History")).not.toBeInTheDocument();
    expect(api.getMyLeaveLedger).not.toHaveBeenCalled();
  });

  it("shows loading state while useLeaveStanding is loading", () => {
    vi.mocked(useLeaveStanding).mockReturnValue({
      isCovered: false,
      isLoading: true,
    });

    renderPage();

    expect(screen.getByText("Loading balance history...")).toBeInTheDocument();
    expect(
      screen.queryByText("Leave isn't tracked for your account."),
    ).not.toBeInTheDocument();
  });
});
