import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

import CompanyHolidaysDialog from "@/pages/Leave/components/CompanyHolidaysDialog";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");

const envelope = (data) => ({ success: true, message: "ok", data });

const nationalDay = {
  name: "National Day",
  startDate: "2026-10-01",
  endDate: "2026-10-03",
  dayCount: 3,
  isExchangeable: true,
};

describe("CompanyHolidaysDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getLeaveHolidayYears.mockResolvedValue(
      envelope({ years: [2026], currentYear: 2026, nextYear: 2027 }),
    );
    api.getLeaveHolidays.mockResolvedValue(
      envelope({ year: 2026, totalDays: 3, segments: [nationalDay] }),
    );
  });

  it("retries the year list when that is what failed", async () => {
    api.getLeaveHolidayYears.mockRejectedValueOnce(new Error("network error"));

    render(<CompanyHolidaysDialog isOpen onClose={() => {}} />);

    await waitFor(() =>
      expect(
        screen.getByText("Couldn't load the calendar."),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() =>
      expect(screen.getByText("National Day")).toBeInTheDocument(),
    );
    expect(api.getLeaveHolidayYears).toHaveBeenCalledTimes(2);
    expect(api.getLeaveHolidays).toHaveBeenCalledWith(2026);
  });

  it("retries the year when only the year failed", async () => {
    api.getLeaveHolidays.mockRejectedValueOnce(new Error("network error"));

    render(<CompanyHolidaysDialog isOpen onClose={() => {}} />);

    await waitFor(() =>
      expect(
        screen.getByText("Couldn't load the calendar."),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() =>
      expect(screen.getByText("National Day")).toBeInTheDocument(),
    );
    expect(api.getLeaveHolidayYears).toHaveBeenCalledTimes(1);
  });
});
