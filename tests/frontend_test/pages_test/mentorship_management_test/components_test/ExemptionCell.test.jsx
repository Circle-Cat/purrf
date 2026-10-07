import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import ExemptionCell from "@/pages/MentorshipManagement/components/ExemptionCell";
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
  requestMatchingExemption: vi.fn(),
  withdrawMentorshipApproval: vi.fn(),
}));

// The request as the search row carries it: approval ids are numbers.
const waiting = {
  requestId: 61,
  action: "exempt_matching",
  person: { userId: 21, name: "Ann Lee" },
  raisedBy: { userId: 9, name: "Ada Ng" },
  reviewer: { userId: 8, name: "Rae Kim" },
};

const rowOf = (exemptionRequest) => ({
  userId: 21,
  firstName: "Ann",
  lastName: "Lee",
  preferredName: "Ann Lee",
  exemptionRequest,
});

const renderCell = (props = {}) => {
  const onChanged = vi.fn(() => Promise.resolve());
  render(
    <ExemptionCell
      row={rowOf(waiting)}
      roundId="7"
      canWrite
      canApprove={false}
      userId={9}
      onChanged={onChanged}
      {...props}
    />,
  );
  return onChanged;
};

describe("ExemptionCell", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    vi.spyOn(toast, "success").mockImplementation(() => {});
    vi.spyOn(toast, "error").mockImplementation(() => {});
    getMentorshipApprovers.mockResolvedValue({
      data: [
        { userId: 8, name: "Rae Kim" },
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

  it("shows nothing without write access when nothing waits", () => {
    const { container } = render(
      <ExemptionCell
        row={rowOf(null)}
        roundId="7"
        canWrite={false}
        canApprove={false}
        userId={9}
        onChanged={vi.fn()}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("lets the raiser hand the request over or withdraw it", async () => {
    const user = userEvent.setup();
    const onChanged = renderCell();

    await user.click(screen.getByRole("button", { name: "Reassign reviewer" }));
    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "Sam Oyelaran" }),
      ).toBeInTheDocument(),
    );
    await user.selectOptions(screen.getByLabelText("Reviewer"), "12");
    await user.click(screen.getByRole("button", { name: "Reassign" }));
    await waitFor(() =>
      expect(reassignMentorshipApproval).toHaveBeenCalledWith(61, 12),
    );

    await user.click(screen.getByRole("button", { name: "Withdraw" }));
    await waitFor(() =>
      expect(withdrawMentorshipApproval).toHaveBeenCalledWith(61),
    );
    expect(onChanged).toHaveBeenCalledTimes(2);
  });

  it("lets the named reviewer reject with a reason", async () => {
    const user = userEvent.setup();
    const onChanged = renderCell({ canApprove: true, userId: 8 });

    await user.click(screen.getByRole("button", { name: "Reject" }));
    await user.type(screen.getByLabelText("Reason"), "Two rounds short");
    await user.click(screen.getAllByRole("button", { name: "Reject" }).at(-1));

    await waitFor(() =>
      expect(decideMentorshipApproval).toHaveBeenCalledWith(61, {
        decision: "reject",
        comment: "Two rounds short",
      }),
    );
    expect(toast.success).toHaveBeenCalledWith("Exemption rejected.");
    expect(onChanged).toHaveBeenCalled();
  });

  it("shows why an approval was refused", async () => {
    const user = userEvent.setup();
    decideMentorshipApproval.mockRejectedValue({
      response: { data: { message: "The round is not in progress." } },
    });
    renderCell({ canApprove: true, userId: 8 });

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.click(screen.getAllByRole("button", { name: "Approve" }).at(-1));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("The round is not in progress."),
    );
  });
});
