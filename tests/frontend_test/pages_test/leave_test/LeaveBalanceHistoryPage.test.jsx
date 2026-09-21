import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import BalanceHistoryPage from "@/pages/Leave/BalanceHistoryPage";
import * as api from "@/api/leaveApi";
import { useLeaveStanding } from "@/pages/Leave/hooks/useLeaveStanding";
import {
  formatBusinessDate,
  LEAVE_CALENDAR_ZONE_LABEL,
} from "@/pages/Leave/utils/leaveDates";

vi.mock("@/api/leaveApi");
vi.mock("@/pages/Leave/hooks/useLeaveStanding");

const envelope = (data) => ({ success: true, message: "ok", data });

describe("BalanceHistoryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useLeaveStanding.mockReturnValue({ isCovered: true, isLoading: false });
  });

  it("shows an empty-state sentence when entries are empty", async () => {
    api.getMyLeaveLedger.mockResolvedValue(
      envelope({
        balanceHours: "0.00",
        entries: [],
      }),
    );

    render(<BalanceHistoryPage />);

    await waitFor(() =>
      expect(
        screen.getByText("No balance history entries found."),
      ).toBeInTheDocument(),
    );

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("displays negative balance without error styling", async () => {
    api.getMyLeaveLedger.mockResolvedValue(
      envelope({
        balanceHours: "-16.00",
        entries: [
          {
            effectiveDate: "2026-05-06",
            entryType: "leave_deduction",
            hours: "-16.00",
            note: null,
          },
        ],
      }),
    );

    render(<BalanceHistoryPage />);

    await waitFor(() =>
      expect(screen.getByText("-16.00 h")).toBeInTheDocument(),
    );

    const balanceElement = screen.getByText("-16.00 h");
    expect(balanceElement.className).not.toMatch(/text-(red|rose)-/);
  });

  it("renders English labels for all 6 entry types and raw value for unrecognised type", async () => {
    api.getMyLeaveLedger.mockResolvedValue(
      envelope({
        balanceHours: "33.54",
        entries: [
          {
            effectiveDate: "2026-01-01",
            entryType: "weekly_accrual",
            hours: "1.54",
            note: null,
          },
          {
            effectiveDate: "2026-01-02",
            entryType: "leave_deduction",
            hours: "-8.00",
            note: null,
          },
          {
            effectiveDate: "2026-01-03",
            entryType: "level_change",
            hours: "0.00",
            note: null,
          },
          {
            effectiveDate: "2026-01-04",
            entryType: "manual_adjustment",
            hours: "40.00",
            note: null,
          },
          {
            effectiveDate: "2026-01-05",
            entryType: "exchange_credit",
            hours: "8.00",
            note: null,
          },
          {
            effectiveDate: "2026-01-06",
            entryType: "carryover_forfeit",
            hours: "-4.00",
            note: null,
          },
          {
            effectiveDate: "2026-01-07",
            entryType: "custom_future_type",
            hours: "0.00",
            note: null,
          }, // 未识别类型
        ],
      }),
    );

    render(<BalanceHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Weekly Accrual")).toBeInTheDocument();
      expect(screen.getByText("Leave Deduction")).toBeInTheDocument();
      expect(screen.getByText("Level Change")).toBeInTheDocument();
      expect(screen.getByText("Manual Adjustment")).toBeInTheDocument();
      expect(screen.getByText("Exchange Credit")).toBeInTheDocument();
      expect(screen.getByText("Carryover Forfeit")).toBeInTheDocument();
      expect(screen.getByText("custom_future_type")).toBeInTheDocument();
    });
  });

  it("renders the timezone once in the footer using LEAVE_CALENDAR_ZONE_LABEL and formats dates", async () => {
    api.getMyLeaveLedger.mockResolvedValue(
      envelope({
        balanceHours: "10.00",
        entries: [
          {
            effectiveDate: "2026-10-01",
            entryType: "weekly_accrual",
            hours: "10.00",
            note: "Test entry",
          },
        ],
      }),
    );

    render(<BalanceHistoryPage />);

    await waitFor(() => {
      expect(
        screen.getByText(formatBusinessDate("2026-10-01")),
      ).toBeInTheDocument();
      expect(screen.getByText(LEAVE_CALENDAR_ZONE_LABEL)).toBeInTheDocument();
    });
  });

  it("renders 'Leave isn't tracked for your account.' and no balance when isCovered is false", async () => {
    useLeaveStanding.mockReturnValue({ isCovered: false, isLoading: false });

    render(<BalanceHistoryPage />);

    expect(
      screen.getByText("Leave isn't tracked for your account."),
    ).toBeInTheDocument();

    expect(screen.queryByText(/0\.00 h/)).not.toBeInTheDocument();
    expect(screen.queryByText("Balance History")).not.toBeInTheDocument();
    expect(api.getMyLeaveLedger).not.toHaveBeenCalled();
  });

  it("shows loading state while useLeaveStanding is loading", () => {
    useLeaveStanding.mockReturnValue({ isCovered: false, isLoading: true });

    render(<BalanceHistoryPage />);

    expect(screen.getByText("Loading balance history...")).toBeInTheDocument();
    expect(
      screen.queryByText("Leave isn't tracked for your account."),
    ).not.toBeInTheDocument();
  });
});
