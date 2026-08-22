import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import LeaveRequestsPage from "@/pages/Leave/RequestsPage";
import * as api from "@/api/leaveApi";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";

vi.mock("@/api/leaveApi");
vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

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
  reason: "Family trip",
  ...overrides,
});

const envelope = (data) => ({ success: true, message: "ok", data });

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/leave/requests"]}>
      <Routes>
        <Route path="/leave/requests" element={<LeaveRequestsPage />} />
        <Route path="/dashboard/me" element={<p>Personal dashboard</p>} />
      </Routes>
    </MemoryRouter>,
  );

describe("LeaveRequestsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.LEAVE_MANAGEMENT]: true });
    api.getLeaveCoverage.mockResolvedValue(envelope({ isCovered: true }));
    api.getMyLeaveRequests.mockResolvedValue(envelope([row()]));
  });

  it("sends somebody away when the feature is switched off", () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.LEAVE_MANAGEMENT]: false,
    });

    renderPage();

    expect(screen.getByText("Personal dashboard")).toBeInTheDocument();
    expect(api.getMyLeaveRequests).not.toHaveBeenCalled();
  });

  it("says leave is not tracked rather than showing an empty list", async () => {
    // An empty list reads as "you have never taken leave", which is a
    // different statement from "this does not apply to you".
    api.getLeaveCoverage.mockResolvedValue(envelope({ isCovered: false }));

    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText(/isn't tracked for your account/i),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByText(/haven't asked for any leave/i),
    ).not.toBeInTheDocument();
  });

  it("waits for coverage rather than bouncing while it loads", () => {
    // Coverage fails closed, so acting on it before it has answered would turn
    // every covered employee away for a moment.
    api.getLeaveCoverage.mockReturnValue(new Promise(() => {}));

    renderPage();

    expect(screen.queryByText(/isn't tracked/i)).not.toBeInTheDocument();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("lists what has been asked for, with the hours the server computed", async () => {
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/Aug 25 – Aug 27, 2026/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/24\.00 h/)).toBeInTheDocument();
  });

  it("says so when nothing has been asked for", async () => {
    api.getMyLeaveRequests.mockResolvedValue(envelope([]));

    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText(/haven't asked for any leave/i),
      ).toBeInTheDocument(),
    );
  });

  it("offers a retry when the list will not load", async () => {
    api.getMyLeaveRequests.mockRejectedValueOnce(new Error("network error"));
    api.getMyLeaveRequests.mockResolvedValue(envelope([row()]));

    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText(/couldn't load your requests/i),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() =>
      expect(screen.getByText(/24\.00 h/)).toBeInTheDocument(),
    );
  });

  it("opens the company holidays for the year the server calls current", async () => {
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

    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/24\.00 h/)).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Company holidays" }));

    await waitFor(() =>
      expect(screen.getByText("National Day")).toBeInTheDocument(),
    );
    expect(api.getLeaveHolidays).toHaveBeenCalledWith(2026);
    expect(screen.getByText(/Oct 1 – Oct 3, 2026/)).toBeInTheDocument();
    expect(screen.getByText("Exchangeable")).toBeInTheDocument();
  });
});
