import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import ApprovalRow from "@/pages/Leave/ApprovalsPage/components/ApprovalRow";

const row = (overrides = {}) => ({
  requestId: 1,
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
  ...overrides,
});

describe("ApprovalRow", () => {
  it("renders the dates the server sent, not the viewer's dates", () => {
    render(
      <ApprovalRow
        row={row()}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.getByText(/Aug 13 – Aug 15, 2026/)).toBeInTheDocument();
  });

  it("names the requester by ldap as well, the way other internal tools do", () => {
    render(
      <ApprovalRow
        row={row()}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.getByText(/Ann Employee/)).toBeInTheDocument();
    expect(screen.getByText(/\(aemployee\)/)).toBeInTheDocument();
  });

  it("shows the name alone when no ldap could be resolved", () => {
    render(
      <ApprovalRow
        row={row({ employeeLdap: null })}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.getByText(/Ann Employee/)).toBeInTheDocument();
    expect(screen.queryByText(/\(\)/)).not.toBeInTheDocument();
  });

  it("marks an exchange as adding hours and paid leave as taking them", () => {
    // The sign is the point: an exchange credits the balance and paid leave
    // deducts, and that is what an approver is deciding about.
    const { rerender } = render(
      <ApprovalRow
        row={row({ type: "exchange" })}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );
    expect(screen.getByText(/\+ Holiday exchange/)).toBeInTheDocument();

    rerender(
      <ApprovalRow
        row={row({ type: "paid" })}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );
    expect(screen.getByText(/\u2212 Paid leave/)).toBeInTheDocument();
  });

  it("gives sick leave no sign, because it moves the balance not at all", () => {
    // Grouping it with paid leave would have the badge assert that sick leave
    // deducts. `_ledger_entry` writes no row for it, not even a zero one.
    render(
      <ApprovalRow
        row={row({ type: "sick" })}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.getByText("Sick leave")).toBeInTheDocument();
    expect(screen.queryByText(/[+\u2212] Sick leave/)).not.toBeInTheDocument();
  });

  it("renders the hours exactly as they arrived", () => {
    // The server is the only place leave arithmetic happens. Reformatting here
    // would let the browser disagree with the ledger without saying so.
    render(
      <ApprovalRow
        row={row({ hours: "7.50" })}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.getByText(/7\.50 h/)).toBeInTheDocument();
  });

  it("asks once more before approving, because approving is irreversible", () => {
    const onDecide = vi.fn();
    render(
      <ApprovalRow
        row={row()}
        isDecidable
        isDeciding={false}
        onDecide={onDecide}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    expect(onDecide).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Yes, approve" }));
    expect(onDecide).toHaveBeenCalledWith(1, true);
  });

  it("rejects without a second question", () => {
    const onDecide = vi.fn();
    render(
      <ApprovalRow
        row={row()}
        isDecidable
        isDeciding={false}
        onDecide={onDecide}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    expect(onDecide).toHaveBeenCalledWith(1, false);
  });

  it("says where the balance lands and where it came from", () => {
    // The pair an approver is deciding on. Both come from the server: the
    // browser doing the arithmetic is how a screen ends up disagreeing with
    // the ledger row the approval writes.
    render(
      <ApprovalRow
        row={row()}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.getByText("Balance after")).toBeInTheDocument();
    expect(screen.getByText("80.25h")).toBeInTheDocument();
    expect(screen.getByText(/from 88\.25h/)).toBeInTheDocument();
  });

  it("renders the figures as they arrived, without recomputing them", () => {
    render(
      <ApprovalRow
        row={row({ balanceBefore: "12.00", balanceAfter: "-12.00" })}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.getByText("-12.00h")).toBeInTheDocument();
    expect(screen.getByText(/from 12\.00h/)).toBeInTheDocument();
  });

  it("says so when approving moves the balance not at all", () => {
    render(
      <ApprovalRow
        row={row({
          type: "sick",
          balanceBefore: "30.00",
          balanceAfter: "30.00",
        })}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.getByText(/unchanged/)).toBeInTheDocument();
  });

  it("shows no landing figure on something already decided", () => {
    // The ledger has already moved, so a number here would read as the balance
    // today rather than a hypothetical.
    render(
      <ApprovalRow
        row={row({
          status: "approved",
          balanceBefore: null,
          balanceAfter: null,
        })}
        isDecidable={false}
        isDeciding={false}
      />,
    );

    expect(screen.queryByText("Balance after")).not.toBeInTheDocument();
  });

  it("flags a request filed with too little notice", () => {
    render(
      <ApprovalRow
        row={row({ isLateNotice: true })}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );

    expect(
      screen.getByText("Submitted with less than 6 working days' notice"),
    ).toBeInTheDocument();
  });

  it("counts the notice in working days, which is what the rule counts", () => {
    // The working week runs Tuesday to Saturday, so six working days is about
    // eight calendar days. Calling them "days" would read as the looser number.
    render(
      <ApprovalRow
        row={row({ isLateNotice: true, requiredNoticeWorkdays: 10 })}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.getByText(/10 working days/)).toBeInTheDocument();
  });

  it("does not repeat the overdraft flag beside the live balance figures", () => {
    // The flag was computed when the request was filed; the figures on the
    // right are computed now. Weekly accrual keeps raising a balance, so a
    // stale flag can contradict the number next to it.
    render(
      <ApprovalRow
        row={row({
          isOverdraft: true,
          balanceBefore: "88.25",
          balanceAfter: "80.25",
        })}
        isDecidable
        isDeciding={false}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.queryByText(/below zero/i)).not.toBeInTheDocument();
    expect(screen.getByText("80.25h")).toBeInTheDocument();
  });

  it("offers no decision on something already settled", () => {
    render(
      <ApprovalRow
        row={row({ status: "approved" })}
        isDecidable={false}
        isDeciding={false}
      />,
    );

    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("names an employee whose account could not be resolved", () => {
    render(
      <ApprovalRow
        row={row({ employeeName: null })}
        isDecidable={false}
        isDeciding={false}
      />,
    );

    expect(screen.getByText(/Unknown employee/)).toBeInTheDocument();
  });
});
