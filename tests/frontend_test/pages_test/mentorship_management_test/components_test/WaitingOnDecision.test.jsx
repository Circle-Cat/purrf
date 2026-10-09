import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import WaitingOnDecision from "@/pages/MentorshipManagement/components/WaitingOnDecision";
import {
  decideMentorshipApproval,
  getMentorshipApprovers,
  reassignMentorshipApproval,
  withdrawMentorshipApproval,
} from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  decideMentorshipApproval: vi.fn(),
  getMentorshipApprovers: vi.fn(),
  reassignMentorshipApproval: vi.fn(),
  requestParticipantMark: vi.fn(),
  requestParticipantWithdrawal: vi.fn(),
  withdrawMentorshipApproval: vi.fn(),
}));

// Raiser 9, reviewer 8, the person 3104: three different people.
const waiting = {
  requestId: 41,
  action: "withdraw_participant",
  raisedBy: { userId: 9, name: "Dana Wu" },
  reviewer: { userId: 8, name: "Rae Kim" },
  reason: "Stopped replying",
  createdAt: "2026-10-09T08:00:00Z",
};

const renderBlock = (props = {}) => {
  const onChanged = vi.fn(() => Promise.resolve());
  const result = render(
    <WaitingOnDecision
      requests={[waiting]}
      personId={3104}
      personName="Mia Ko"
      viewerId={9}
      canApprove={false}
      actionsOn
      onChanged={onChanged}
      {...props}
    />,
  );
  return { ...result, onChanged };
};

describe("WaitingOnDecision", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    vi.spyOn(toast, "success").mockImplementation(() => {});
    vi.spyOn(toast, "error").mockImplementation(() => {});
    getMentorshipApprovers.mockResolvedValue({
      data: [
        { userId: 8, name: "Rae Kim" },
        { userId: 3104, name: "Mia Ko" },
        { userId: 12, name: "Sam Oyelaran" },
      ],
    });
    for (const call of [
      decideMentorshipApproval,
      reassignMentorshipApproval,
      withdrawMentorshipApproval,
    ]) {
      call.mockResolvedValue({ data: {} });
    }
  });

  it("shows nothing when nothing waits", () => {
    const { container } = renderBlock({ requests: [] });
    expect(container).toBeEmptyDOMElement();
  });

  it("says what waits, who raised it and who decides", () => {
    renderBlock({ viewerId: 77 });

    const block = screen.getByRole("region", { name: "Waiting on a decision" });
    expect(
      within(block).getByText(
        "Withdrawal from round — raised by Dana Wu · sent to Rae Kim",
      ),
    ).toBeInTheDocument();
    expect(within(block).queryAllByRole("button")).toHaveLength(0);
  });

  it("lets the raiser withdraw the request or hand it to another reviewer", async () => {
    const user = userEvent.setup();
    const { onChanged } = renderBlock();

    expect(
      screen.queryByRole("button", { name: "Approve" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reassign" }));
    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "Sam Oyelaran" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("option", { name: "Rae Kim" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "Mia Ko" }),
    ).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Reviewer"), "12");
    await user.click(
      screen.getAllByRole("button", { name: "Reassign" }).at(-1),
    );
    await waitFor(() =>
      expect(reassignMentorshipApproval).toHaveBeenCalledWith(41, 12),
    );

    await user.click(screen.getByRole("button", { name: "Withdraw" }));
    await waitFor(() =>
      expect(withdrawMentorshipApproval).toHaveBeenCalledWith(41),
    );
    expect(onChanged).toHaveBeenCalledTimes(2);
  });

  it("lets only the named reviewer approve, after reading what it does", async () => {
    const user = userEvent.setup();
    renderBlock({ viewerId: 8, canApprove: true });

    expect(
      screen.queryByRole("button", { name: "Withdraw" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(screen.getByText(/cannot be undone/)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Approve" }).at(-1));

    await waitFor(() =>
      expect(decideMentorshipApproval).toHaveBeenCalledWith(41, {
        decision: "approve",
        comment: undefined,
      }),
    );
    expect(toast.success).toHaveBeenCalledWith("Request approved.");
  });

  it("lets the named reviewer reject with a reason", async () => {
    const user = userEvent.setup();
    renderBlock({ viewerId: 8, canApprove: true });

    await user.click(screen.getByRole("button", { name: "Reject" }));
    await user.type(screen.getByLabelText("Reason"), "She replied today");
    await user.click(screen.getAllByRole("button", { name: "Reject" }).at(-1));

    await waitFor(() =>
      expect(decideMentorshipApproval).toHaveBeenCalledWith(41, {
        decision: "reject",
        comment: "She replied today",
      }),
    );
  });

  it("gives an approver who is not the named reviewer no buttons", () => {
    renderBlock({ viewerId: 12, canApprove: true });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("offers no actions while approvals are switched off", () => {
    renderBlock({ actionsOn: false, viewerId: 8, canApprove: true });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(
      screen.getByText(/raised by Dana Wu · sent to Rae Kim/),
    ).toBeInTheDocument();
  });
});
