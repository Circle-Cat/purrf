import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import TimeOffCard from "@/pages/PersonalDashboard/components/TimeOffCard";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");

const envelope = (data) => ({ success: true, message: "ok", data });

const row = (overrides = {}) => ({
  requestId: 1,
  type: "paid",
  status: "pending",
  startDate: "2026-08-25",
  endDate: "2026-08-27",
  startTime: null,
  endTime: null,
  hours: "24.00",
  isLateNotice: false,
  requiredNoticeWorkdays: 6,
  reason: null,
  ...overrides,
});

const renderCard = (props = {}) =>
  render(
    <MemoryRouter initialEntries={["/dashboard/me"]}>
      <Routes>
        <Route
          path="/dashboard/me"
          element={
            <TimeOffCard
              availableHours="56.00"
              pendingHours="24.00"
              usedHours="8.00"
              {...props}
            />
          }
        />
        <Route path="/leave/requests" element={<p>My requests page</p>} />
      </Routes>
    </MemoryRouter>,
  );

describe("TimeOffCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMyLeaveRequests.mockResolvedValue(envelope([]));
  });

  it("shows the three figures the server computed", async () => {
    renderCard();

    await waitFor(() => expect(screen.getByText("56.00h")).toBeInTheDocument());
    expect(screen.getByText("24.00h")).toBeInTheDocument();
    expect(screen.getByText("8.00h")).toBeInTheDocument();
  });

  it("renders the figures as they arrived, deriving only the days hint", async () => {
    // Available already has undecided requests held back, which is the same
    // definition the overdraft mark uses. Recomputing it here could tell
    // somebody they can afford leave that filing would then flag.
    renderCard({ availableHours: "56.00" });

    await waitFor(() => expect(screen.getByText("56.00h")).toBeInTheDocument());
    expect(screen.getByText("7.0 days")).toBeInTheDocument();
  });

  it("colours a negative balance without treating it as an error", async () => {
    // An L1 has no entitlement and may still take paid leave.
    renderCard({ availableHours: "-8.00" });

    await waitFor(() => expect(screen.getByText("-8.00h")).toBeInTheDocument());
  });

  it("counts what is awaiting a decision", async () => {
    api.getMyLeaveRequests.mockResolvedValue(
      envelope([
        row(),
        row({ requestId: 2 }),
        row({ requestId: 3, status: "approved" }),
      ]),
    );

    renderCard();

    await waitFor(() =>
      expect(screen.getByText("2 awaiting a decision")).toBeInTheDocument(),
    );
  });

  it("says nothing about pending decisions when there are none", async () => {
    renderCard();

    await waitFor(() =>
      expect(screen.getByText("Time off")).toBeInTheDocument(),
    );
    expect(screen.queryByText(/awaiting a decision/)).not.toBeInTheDocument();
  });

  it("opens the request dialog on the card rather than a page away", async () => {
    renderCard();
    await waitFor(() =>
      expect(screen.getByText("Time off")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Request time off" }));

    expect(screen.getByText("Request leave")).toBeInTheDocument();
  });

  it("opens the company holidays on the card too", async () => {
    api.getLeaveHolidayYears.mockResolvedValue(
      envelope({ years: [2026], currentYear: 2026, nextYear: 2027 }),
    );
    api.getLeaveHolidays.mockResolvedValue(
      envelope({
        year: 2026,
        totalDays: 3,
        segments: [
          {
            name: "National Day",
            startDate: "2026-10-01",
            endDate: "2026-10-03",
            dayCount: 3,
            isExchangeable: true,
          },
        ],
      }),
    );

    renderCard();
    await waitFor(() =>
      expect(screen.getByText("Time off")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Company holidays" }));

    await waitFor(() =>
      expect(screen.getByText("National Day")).toBeInTheDocument(),
    );
    expect(api.getLeaveHolidays).toHaveBeenCalledWith(2026);
  });

  it("sends the history to a page of its own", async () => {
    // A dashboard card that expands into a long list stops being a dashboard
    // card, so the list is a page and this only links to it.
    renderCard();
    await waitFor(() =>
      expect(screen.getByText("Time off")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "My requests" }));

    expect(screen.getByText("My requests page")).toBeInTheDocument();
  });
});
