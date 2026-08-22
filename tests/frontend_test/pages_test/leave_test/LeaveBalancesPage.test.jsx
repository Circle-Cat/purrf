import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import LeaveBalancesPage from "@/pages/Leave/BalancesPage";
import * as api from "@/api/leaveApi";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";

vi.mock("@/api/leaveApi");
vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

const envelope = (data) => ({ success: true, message: "ok", data });

const person = (overrides = {}) => ({
  userId: 10,
  ldap: "ann",
  name: "Ann Employee",
  level: "L3",
  annualHours: 80,
  balanceHours: "72.00",
  ...overrides,
});

const overview = (overrides = {}) => ({
  people: [person()],
  excluded: {
    left: [],
    noHireDate: [],
    unreadable: [],
    unresolved: [],
    notInternal: [],
  },
  profileCount: 1,
  ...overrides,
});

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/leave/balances"]}>
      <Routes>
        <Route path="/leave/balances" element={<LeaveBalancesPage />} />
        <Route path="/dashboard/me" element={<p>Personal dashboard</p>} />
      </Routes>
    </MemoryRouter>,
  );

describe("LeaveBalancesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.LEAVE_MANAGEMENT]: true });
    api.getLeaveBalances.mockResolvedValue(envelope(overview()));
  });

  it("sends somebody away when the feature is switched off", () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.LEAVE_MANAGEMENT]: false,
    });

    renderPage();

    expect(screen.getByText("Personal dashboard")).toBeInTheDocument();
    expect(api.getLeaveBalances).not.toHaveBeenCalled();
  });

  it("counts who is accruing against the profiles considered", async () => {
    // So a reader does not have to add the exclusion lists up and hope the
    // total matches.
    api.getLeaveBalances.mockResolvedValue(
      envelope(overview({ profileCount: 5 })),
    );

    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText(/Accruing: 1 of 5 directory profiles/),
      ).toBeInTheDocument(),
    );
  });

  it("keeps each way of being left out apart, with what fixes it", async () => {
    // One list would hide that a missing hire date is an Azure fix while an
    // unresolved ldap is a purrf account that does not exist.
    api.getLeaveBalances.mockResolvedValue(
      envelope(
        overview({
          excluded: {
            left: ["zoe"],
            noHireDate: ["carol"],
            unreadable: [],
            unresolved: ["dave"],
            notInternal: [],
          },
        }),
      ),
    );

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/No purrf account — 1/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/No hire date in Azure — 1/)).toBeInTheDocument();
    expect(screen.getByText(/Left — 1/)).toBeInTheDocument();
    expect(screen.queryByText(/Unreadable profile/)).not.toBeInTheDocument();
  });

  it("says so when nobody is accruing, and names the likely cause", async () => {
    api.getLeaveBalances.mockResolvedValue(
      envelope(overview({ people: [], profileCount: 0 })),
    );

    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText(/nightly sync may not have run/i),
      ).toBeInTheDocument(),
    );
  });

  it("asks once more before writing a correction, because it cannot be undone", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Ann Employee")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Correct" }));
    fireEvent.change(screen.getByLabelText("Hours"), {
      target: { value: "-8.00" },
    });
    fireEvent.change(screen.getByLabelText("Effective date"), {
      target: { value: "2026-08-20" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Write the correction" }),
    );

    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument();
    expect(api.adjustLeaveBalance).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Yes, write it" }));

    await waitFor(() => expect(api.adjustLeaveBalance).toHaveBeenCalled());
    expect(api.adjustLeaveBalance.mock.calls[0][0]).toEqual({
      userId: 10,
      hours: "-8.00",
      effectiveDate: "2026-08-20",
      note: "",
    });
  });

  it("shows the balance the server computed, not one added up here", async () => {
    api.adjustLeaveBalance.mockResolvedValue(
      envelope({
        userId: 10,
        hours: "-8.00",
        effectiveDate: "2026-08-20",
        note: "Leave taken in March",
        balanceHours: "64.00",
      }),
    );

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Ann Employee")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Correct" }));
    fireEvent.change(screen.getByLabelText("Hours"), {
      target: { value: "-8.00" },
    });
    fireEvent.change(screen.getByLabelText("Effective date"), {
      target: { value: "2026-08-20" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Write the correction" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Yes, write it" }));

    await waitFor(() =>
      expect(screen.getByText(/balance is now 64\.00 h/)).toBeInTheDocument(),
    );
  });

  it("shows the server's refusal", async () => {
    api.adjustLeaveBalance.mockRejectedValue(
      Object.assign(new Error("Request failed"), {
        response: {
          data: { message: "A leave adjustment needs a note saying why." },
        },
      }),
    );

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Ann Employee")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Correct" }));
    fireEvent.change(screen.getByLabelText("Hours"), {
      target: { value: "8.00" },
    });
    fireEvent.change(screen.getByLabelText("Effective date"), {
      target: { value: "2026-08-20" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Write the correction" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Yes, write it" }));

    await waitFor(() =>
      expect(
        screen.getByText("A leave adjustment needs a note saying why."),
      ).toBeInTheDocument(),
    );
  });

  it("corrects the person whose row was clicked, with no id to mistype", async () => {
    api.getLeaveBalances.mockResolvedValue(
      envelope(
        overview({
          people: [
            person(),
            person({ userId: 11, ldap: "bob", name: "Bob Report" }),
          ],
          profileCount: 2,
        }),
      ),
    );
    api.adjustLeaveBalance.mockResolvedValue(
      envelope({
        userId: 11,
        hours: "8.00",
        effectiveDate: "2026-08-20",
        note: "",
        balanceHours: "80.00",
      }),
    );

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Bob Report")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Correct" })[1]);
    expect(
      screen.getByText(/Correct Bob Report's balance/),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Hours"), {
      target: { value: "8.00" },
    });
    fireEvent.change(screen.getByLabelText("Effective date"), {
      target: { value: "2026-08-20" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Write the correction" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Yes, write it" }));

    await waitFor(() => expect(api.adjustLeaveBalance).toHaveBeenCalled());
    expect(api.adjustLeaveBalance.mock.calls[0][0].userId).toBe(11);
  });
});
