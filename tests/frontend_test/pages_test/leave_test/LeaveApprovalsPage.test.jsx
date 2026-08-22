import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

import { MemoryRouter, Route, Routes } from "react-router-dom";

import LeaveApprovalsPage from "@/pages/Leave/ApprovalsPage";
import * as api from "@/api/leaveApi";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";

vi.mock("@/api/leaveApi");
vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

const row = (overrides = {}) => ({
  requestId: 1,
  userId: 10,
  employeeName: "Ann Employee",
  employeeLdap: "aemployee",
  requiredNoticeWorkdays: 6,
  balanceBefore: "88.25",
  balanceAfter: "80.25",
  type: "paid",
  status: "pending",
  startDate: "2026-08-13",
  endDate: "2026-08-15",
  startTime: null,
  endTime: null,
  hours: "24.00",
  isOverdraft: false,
  isLateNotice: false,
  reason: "Holiday",
  approverUserId: 20,
  decidedBy: null,
  decidedAt: null,
  ...overrides,
});

const envelope = (rows) => ({ success: true, message: "ok", data: rows });

describe("LeaveApprovalsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.LEAVE_MANAGEMENT]: true });
  });

  it("sends somebody away when the feature is switched off", () => {
    // Covering the address, not only the dashboard card: hiding the way in
    // while leaving the page reachable by typing its path is not switched off.
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.LEAVE_MANAGEMENT]: false,
    });

    render(
      <MemoryRouter initialEntries={["/leave/approvals"]}>
        <Routes>
          <Route path="/leave/approvals" element={<LeaveApprovalsPage />} />
          <Route path="/dashboard/me" element={<p>Personal dashboard</p>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Personal dashboard")).toBeInTheDocument();
    expect(api.getLeaveApprovals).not.toHaveBeenCalled();
  });

  it("separates what is waiting from what was decided", async () => {
    api.getLeaveApprovals.mockResolvedValue(
      envelope([
        row({ requestId: 1, employeeName: "Ann Employee" }),
        row({
          requestId: 2,
          employeeName: "Bob Report",
          status: "rejected",
          decidedBy: 20,
        }),
      ]),
    );

    render(<LeaveApprovalsPage />);

    await waitFor(() =>
      expect(screen.getByText("Waiting on you")).toBeInTheDocument(),
    );
    expect(screen.getByText("Decided")).toBeInTheDocument();
    expect(screen.getByText(/Ann Employee/)).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("shows an empty page rather than a refusal to somebody who approves for nobody", async () => {
    // There is no manager permission to check, so the page cannot be gated.
    api.getLeaveApprovals.mockResolvedValue(envelope([]));

    render(<LeaveApprovalsPage />);

    await waitFor(() =>
      expect(
        screen.getByText(/nothing is waiting on you/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/nothing decided yet/i)).toBeInTheDocument();
  });

  it("offers a retry when the list will not load", async () => {
    api.getLeaveApprovals.mockRejectedValueOnce(new Error("network error"));
    api.getLeaveApprovals.mockResolvedValue(envelope([row()]));

    render(<LeaveApprovalsPage />);

    await waitFor(() =>
      expect(
        screen.getByText(/couldn't load your approvals/i),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() =>
      expect(screen.getByText(/Ann Employee/)).toBeInTheDocument(),
    );
  });

  it("says a failed decision recorded nothing", async () => {
    api.getLeaveApprovals.mockResolvedValue(envelope([row()]));
    api.decideLeaveRequest.mockRejectedValue(new Error("network error"));

    render(<LeaveApprovalsPage />);
    await waitFor(() =>
      expect(screen.getByText(/Ann Employee/)).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    await waitFor(() =>
      expect(screen.getByText(/nothing was recorded/i)).toBeInTheDocument(),
    );
  });

  it("names the calendar the dates belong to", async () => {
    api.getLeaveApprovals.mockResolvedValue(envelope([]));

    render(<LeaveApprovalsPage />);

    await waitFor(() =>
      expect(screen.getByText(/Shanghai/)).toBeInTheDocument(),
    );
  });
});
