import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import PublishApproval from "@/pages/MentorshipManagement/components/PublishApproval";
import {
  decideMentorshipApproval,
  getMentorshipApprovers,
  reassignMentorshipApproval,
  requestMatchingPublish,
  withdrawMentorshipApproval,
} from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  decideMentorshipApproval: vi.fn(),
  getMentorshipApprovers: vi.fn(),
  reassignMentorshipApproval: vi.fn(),
  requestMatchingPublish: vi.fn(),
  withdrawMentorshipApproval: vi.fn(),
}));

const RAISER = "9";
const REVIEWER = "8";

// The overview as the API sends it: user ids on a run are strings.
const overviewOf = (overrides = {}) => ({
  status: "succeeded",
  matchedCount: 12,
  editLock: null,
  problems: [],
  publishRequest: null,
  lastPublishRejection: null,
  ...overrides,
});

const pending = {
  requestId: 31,
  reviewer: { userId: REVIEWER, name: "Rae Kim" },
  raisedBy: { userId: RAISER, name: "Ada Ng" },
  reason: "Reviewed every pair",
  createdAt: "2026-10-07T09:30:00+00:00",
};

const renderPanel = (props = {}) => {
  const onChanged = vi.fn(() => Promise.resolve());
  render(
    <PublishApproval
      roundId="7"
      overview={overviewOf()}
      editing={false}
      canWrite
      canApprove={false}
      userId={9}
      onChanged={onChanged}
      {...props}
    />,
  );
  return onChanged;
};

describe("PublishApproval", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    // Spied, not mocked: a bare-specifier vi.mock does not reach the
    // component's import under bazel.
    vi.spyOn(toast, "success").mockImplementation(() => {});
    vi.spyOn(toast, "error").mockImplementation(() => {});
    getMentorshipApprovers.mockResolvedValue({
      data: [{ userId: 8, name: "Rae Kim" }],
    });
    for (const call of [
      requestMatchingPublish,
      reassignMentorshipApproval,
      decideMentorshipApproval,
      withdrawMentorshipApproval,
    ]) {
      call.mockResolvedValue({ data: {} });
    }
  });

  it("sends a request to the chosen reviewer and reloads", async () => {
    const user = userEvent.setup();
    const onChanged = renderPanel();

    await user.click(
      screen.getByRole("button", { name: "Request publishing" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "Rae Kim" }),
      ).toBeInTheDocument(),
    );
    await user.selectOptions(screen.getByLabelText("Reviewer"), "8");
    await user.type(
      screen.getByLabelText("Reason (optional)"),
      "Reviewed every pair",
    );
    await user.click(screen.getByRole("button", { name: "Send request" }));

    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(requestMatchingPublish).toHaveBeenCalledWith("7", {
      reviewerId: 8,
      reason: "Reviewed every pair",
    });
    expect(toast.success).toHaveBeenCalledWith("Sent for approval.");
  });

  it("cannot be asked for while editing, locked or with problems", () => {
    const blocked = [
      { editing: true },
      { overview: overviewOf({ editLock: { userId: "5", name: "Bo" } }) },
      { overview: overviewOf({ problems: [{ code: "no_reason" }] }) },
    ];
    for (const props of blocked) {
      const { unmount } = render(
        <PublishApproval
          roundId="7"
          overview={overviewOf()}
          editing={false}
          canWrite
          canApprove={false}
          userId={9}
          onChanged={vi.fn()}
          {...props}
        />,
      );
      expect(
        screen.getByRole("button", { name: "Request publishing" }),
      ).toBeDisabled();
      unmount();
    }
  });

  it("shows nothing to someone without write access when nothing waits", () => {
    renderPanel({ canWrite: false });

    expect(
      screen.queryByRole("button", { name: "Request publishing" }),
    ).not.toBeInTheDocument();
  });

  it("shows the last rejection under the button", () => {
    renderPanel({
      overview: overviewOf({
        lastPublishRejection: {
          comment: "Mia is away until May",
          decidedBy: { userId: REVIEWER, name: "Rae Kim" },
          decidedAt: "2026-10-07T11:00:00+00:00",
        },
      }),
    });

    expect(
      screen.getByText(
        "Publishing was rejected by Rae Kim: Mia is away until May",
      ),
    ).toBeInTheDocument();
  });

  it("tells everyone who a waiting request was sent to and by whom", () => {
    renderPanel({
      overview: overviewOf({ publishRequest: pending }),
      userId: 44,
      canWrite: true,
    });

    expect(
      screen.getByText("Waiting for approval — sent to Rae Kim by Ada Ng."),
    ).toBeInTheDocument();
    expect(screen.getByText("Reason: Reviewed every pair")).toBeInTheDocument();
    for (const name of ["Approve", "Reject", "Reassign reviewer", "Withdraw"]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("lets the raiser withdraw or hand the request to another reviewer", async () => {
    const user = userEvent.setup();
    getMentorshipApprovers.mockResolvedValue({
      data: [
        { userId: 8, name: "Rae Kim" },
        { userId: 12, name: "Sam Oyelaran" },
      ],
    });
    const onChanged = renderPanel({
      overview: overviewOf({ publishRequest: pending }),
    });

    await user.click(screen.getByRole("button", { name: "Reassign reviewer" }));
    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "Sam Oyelaran" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("option", { name: "Rae Kim" }),
    ).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Reviewer"), "12");
    await user.click(screen.getByRole("button", { name: "Reassign" }));
    await waitFor(() =>
      expect(reassignMentorshipApproval).toHaveBeenCalledWith(31, 12),
    );

    await user.click(screen.getByRole("button", { name: "Withdraw" }));
    await waitFor(() =>
      expect(withdrawMentorshipApproval).toHaveBeenCalledWith(31),
    );
    expect(onChanged).toHaveBeenCalledTimes(2);
  });

  it("lets the named reviewer approve after confirming", async () => {
    const user = userEvent.setup();
    const onChanged = renderPanel({
      overview: overviewOf({ publishRequest: pending }),
      canApprove: true,
      userId: 8,
    });

    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(screen.getByText(/This creates 12 pairs/)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Approve" }).at(-1));

    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(decideMentorshipApproval).toHaveBeenCalledWith(31, {
      decision: "approve",
      comment: undefined,
    });
    expect(toast.success).toHaveBeenCalledWith(
      "Published. The pairs are in place.",
    );
  });

  it("lets the named reviewer reject with a reason", async () => {
    const user = userEvent.setup();
    renderPanel({
      overview: overviewOf({ publishRequest: pending }),
      canApprove: true,
      userId: 8,
    });

    await user.click(screen.getByRole("button", { name: "Reject" }));
    await user.type(screen.getByLabelText("Reason"), "Mia is away");
    await user.click(screen.getAllByRole("button", { name: "Reject" }).at(-1));

    await waitFor(() =>
      expect(decideMentorshipApproval).toHaveBeenCalledWith(31, {
        decision: "reject",
        comment: "Mia is away",
      }),
    );
  });

  it("shows why an approval was refused and keeps the request", async () => {
    const user = userEvent.setup();
    decideMentorshipApproval.mockRejectedValue({
      response: {
        status: 409,
        data: { message: "Ann Lee is blocked." },
      },
    });
    const onChanged = renderPanel({
      overview: overviewOf({ publishRequest: pending }),
      canApprove: true,
      userId: 8,
    });

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.click(screen.getAllByRole("button", { name: "Approve" }).at(-1));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Ann Lee is blocked."),
    );
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("does not offer decisions to a reviewer who lacks mentorship.approve", () => {
    renderPanel({
      overview: overviewOf({ publishRequest: pending }),
      canApprove: false,
      userId: 8,
    });

    expect(
      screen.queryByRole("button", { name: "Approve" }),
    ).not.toBeInTheDocument();
  });
});
