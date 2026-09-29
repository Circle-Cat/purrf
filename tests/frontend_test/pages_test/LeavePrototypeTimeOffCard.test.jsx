import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TimeOffCard from "@/pages/LeavePrototype/TimeOffCard";
import ManagerView from "@/pages/LeavePrototype/ManagerView";

const figures = { available: 42.2, pending: 8, used: 16 };

const renderCard = (props) =>
  render(
    <TimeOffCard
      {...figures}
      onViewHolidays={() => {}}
      onViewApprovals={() => {}}
      {...props}
    />,
  );

describe("Leave prototype — Time off card", () => {
  it("shows a covered non-approver the figures and no Approvals button", () => {
    renderCard({ isCovered: true, isApprover: false });

    expect(screen.getByText("42.20h")).toBeInTheDocument();
    for (const name of [
      "Request time off",
      "Company holidays",
      "My requests",
      "Balance history",
    ]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
    expect(screen.queryByRole("button", { name: /^Approvals/ })).toBeNull();
  });

  it("adds Approvals with the count for a covered approver", () => {
    renderCard({ isCovered: true, isApprover: true, approvalsPendingCount: 2 });

    expect(screen.getByText("42.20h")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Approvals (2)" }),
    ).toBeInTheDocument();
  });

  it("drops the count when nothing is waiting", () => {
    renderCard({ isCovered: true, isApprover: true, approvalsPendingCount: 0 });

    expect(
      screen.getByRole("button", { name: "Approvals" }),
    ).toBeInTheDocument();
  });

  it("shows an approver outside the population no figures and no filing", () => {
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
    for (const text of ["Available", "Pending", "Used"]) {
      expect(screen.queryByText(text)).toBeNull();
    }
    expect(screen.queryByText(/\d+\.\d{2}h/)).toBeNull();
    for (const name of ["Request time off", "My requests", "Balance history"]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
  });

  it("never says anything is awaiting a decision", () => {
    renderCard({ isCovered: true, isApprover: true, approvalsPendingCount: 2 });

    expect(screen.queryByText(/awaiting a decision/)).toBeNull();
  });

  it("renders nothing for somebody neither covered nor an approver", () => {
    const { container } = renderCard({ isCovered: false, isApprover: false });

    expect(container).toBeEmptyDOMElement();
  });

  it("opens the approvals from its button", async () => {
    const user = userEvent.setup();
    const onViewApprovals = vi.fn();
    renderCard({
      isCovered: true,
      isApprover: true,
      approvalsPendingCount: 2,
      onViewApprovals,
    });

    await user.click(screen.getByRole("button", { name: "Approvals (2)" }));

    expect(onViewApprovals).toHaveBeenCalledTimes(1);
  });
});

describe("Leave prototype — manager dashboard", () => {
  const queue = [
    {
      id: 1,
      userName: "Dana Whitfield",
      userLevel: "L3",
      type: "paid",
      startDate: "2026-10-13",
      endDate: "2026-10-14",
      hours: 16,
      status: "pending",
      balanceBefore: 42.2,
    },
  ];

  it("reaches the queue from the Time off card and comes back", async () => {
    const user = userEvent.setup();
    render(
      <ManagerView queue={queue} onApprove={() => {}} onReject={() => {}} />,
    );

    await user.click(screen.getByRole("button", { name: "Approvals (1)" }));
    expect(
      screen.getByRole("heading", { name: "Approvals" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Dana Whitfield")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Back to dashboard" }));
    expect(
      screen.getByRole("heading", { name: "Personal dashboard" }),
    ).toBeInTheDocument();
  });

  it("hides the manager's figures once she is outside the population", async () => {
    const user = userEvent.setup();
    render(
      <ManagerView queue={queue} onApprove={() => {}} onReject={() => {}} />,
    );
    expect(screen.getByText("Available")).toBeInTheDocument();

    await user.click(
      screen.getByRole("radio", { name: "Outside the leave population" }),
    );

    expect(screen.queryByText("Available")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Approvals (1)" }),
    ).toBeInTheDocument();
  });
});
