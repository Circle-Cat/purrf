import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import TimeOffCard from "@/pages/PersonalDashboard/components/TimeOffCard";
import { useLeaveEnabled } from "@/pages/Leave/hooks/useLeaveEnabled";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");
vi.mock("@/pages/Leave/hooks/useLeaveEnabled", () => ({
  useLeaveEnabled: vi.fn(() => true),
}));

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
              isCovered
              isApprover={false}
              approvalsPendingCount={0}
              availableHours="56.00"
              pendingHours="24.00"
              usedHours="8.00"
              {...props}
            />
          }
        />
        <Route path="/leave/requests" element={<p>My requests page</p>} />
        <Route path="/leave/approvals" element={<p>Approvals page</p>} />
        <Route
          path="/leave/balance-history"
          element={<p>Balance history page</p>}
        />
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

  it("says nothing is awaiting a decision, even with requests of your own pending", async () => {
    // Beside an Approvals button it would read as "waiting on you"; your own
    // undecided hours are already the Pending figure.
    api.getMyLeaveRequests.mockResolvedValue(
      envelope([row(), row({ requestId: 2 })]),
    );

    renderCard({ isApprover: true, approvalsPendingCount: 2 });

    await waitFor(() =>
      expect(api.getMyLeaveRequests).toHaveBeenCalledTimes(1),
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

  it("offers no way into approvals to somebody nobody files against", async () => {
    renderCard();
    await waitFor(() =>
      expect(screen.getByText("Time off")).toBeInTheDocument(),
    );

    expect(
      screen.queryByRole("button", { name: /^Approvals/ }),
    ).not.toBeInTheDocument();
  });
});

describe("TimeOffCard for an approver", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMyLeaveRequests.mockResolvedValue(envelope([]));
  });

  it("adds Approvals, with the count, beside the covered viewer's own buttons", async () => {
    renderCard({ isApprover: true, approvalsPendingCount: 2 });

    await waitFor(() => expect(screen.getByText("56.00h")).toBeInTheDocument());
    for (const name of [
      "Request time off",
      "Company holidays",
      "My requests",
    ]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
    expect(
      screen.getByRole("button", { name: "Approvals (2)" }),
    ).toBeInTheDocument();
  });

  it("drops the count when nothing is waiting", () => {
    // Somebody who has decided everything still needs to get at what they
    // decided, so the way in stays.
    renderCard({ isApprover: true, approvalsPendingCount: 0 });

    expect(
      screen.getByRole("button", { name: "Approvals" }),
    ).toBeInTheDocument();
  });

  it("opens the approvals page", () => {
    renderCard({ isApprover: true, approvalsPendingCount: 2 });

    fireEvent.click(screen.getByRole("button", { name: "Approvals (2)" }));

    expect(screen.getByText("Approvals page")).toBeInTheDocument();
  });

  it("shows an approver outside the leave population no figures and no filing", () => {
    // They have no entitlement: 0.00h under Available would read as "my leave
    // is zero", and the server would refuse anything they filed.
    renderCard({
      isCovered: false,
      isApprover: true,
      approvalsPendingCount: 3,
    });

    expect(
      screen.getByRole("button", { name: "Approvals (3)" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Company holidays" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Leave isn't tracked for your account."),
    ).toBeInTheDocument();
    for (const label of ["Available", "Pending", "Used"]) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
    expect(screen.queryByText(/\d+\.\d{2}h/)).not.toBeInTheDocument();
    for (const name of ["Request time off", "My requests", "Balance history"]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("does not fetch the requests of somebody outside the population", async () => {
    renderCard({
      isCovered: false,
      isApprover: true,
      approvalsPendingCount: 1,
    });

    await waitFor(() =>
      expect(screen.getByText("Time off")).toBeInTheDocument(),
    );
    expect(api.getMyLeaveRequests).not.toHaveBeenCalled();
  });

  it("renders nothing for somebody neither covered nor an approver", () => {
    const { container } = renderCard({ isCovered: false, isApprover: false });

    expect(container).toBeEmptyDOMElement();
    expect(api.getMyLeaveRequests).not.toHaveBeenCalled();
  });

  it("sends the balance history to a page of its own", async () => {
    renderCard();
    await waitFor(() =>
      expect(screen.getByText("Time off")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Balance history" }));

    expect(screen.getByText("Balance history page")).toBeInTheDocument();
  });

  it("hides balance history button when leave is disabled", async () => {
    useLeaveEnabled.mockReturnValue(false);

    renderCard();
    await waitFor(() =>
      expect(screen.getByText("Time off")).toBeInTheDocument(),
    );

    expect(
      screen.queryByRole("button", { name: "Balance history" }),
    ).not.toBeInTheDocument();
  });
});
