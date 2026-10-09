import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import ChangeStatusDialog from "@/pages/MentorshipManagement/components/ChangeStatusDialog";
import { statusRequestType } from "@/pages/MentorshipManagement/utils/statusRequestTypes";
import {
  getMentorshipApprovers,
  requestParticipantMark,
  requestParticipantWithdrawal,
} from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  getMentorshipApprovers: vi.fn(),
  requestParticipantMark: vi.fn(),
  requestParticipantWithdrawal: vi.fn(),
}));

// The person (3104) is also an approver here, so leaving them out of the
// picker is something the dialog has to do.
const APPROVERS = [
  { userId: 8, name: "Rae Kim" },
  { userId: 3104, name: "Mia Ko" },
  { userId: 12, name: "Sam Oyelaran" },
];

const renderDialog = (props = {}) => {
  const onOpenChange = vi.fn();
  const onSent = vi.fn(() => Promise.resolve());
  render(
    <ChangeStatusDialog
      open
      onOpenChange={onOpenChange}
      person={{ userId: 3104, name: "Mia Ko" }}
      roundId={7}
      types={[statusRequestType("withdraw_participant")]}
      pairs={[]}
      pendingRequests={[]}
      onSent={onSent}
      {...props}
    />,
  );
  return { onOpenChange, onSent };
};

const pairWith = (pairId, firstName, isActive = true) => ({
  pairId,
  partner: { firstName, lastName: "Lee", preferredName: null, isActive },
});

const pickReviewerAndSend = async (user) => {
  await waitFor(() =>
    expect(screen.getByRole("option", { name: "Rae Kim" })).toBeInTheDocument(),
  );
  await user.selectOptions(screen.getByLabelText("Reviewer"), "8");
  await user.click(screen.getByRole("button", { name: "Send for approval" }));
};

describe("ChangeStatusDialog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    vi.spyOn(toast, "success").mockImplementation(() => {});
    vi.spyOn(toast, "error").mockImplementation(() => {});
    getMentorshipApprovers.mockResolvedValue({ data: APPROVERS });
    requestParticipantWithdrawal.mockResolvedValue({ data: {} });
    requestParticipantMark.mockResolvedValue({ data: {} });
  });

  it("names the only type instead of offering a choice, and says what it does", async () => {
    renderDialog();

    expect(screen.getByText("Withdraw from round")).toBeInTheDocument();
    expect(
      screen.queryByLabelText("What are you asking for"),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/cannot be undone/)).toBeInTheDocument();
    expect(screen.getByText(/partners stay matched/)).toBeInTheDocument();
  });

  it("leaves the person out of the reviewers and sends with an optional reason", async () => {
    const user = userEvent.setup();
    const { onOpenChange, onSent } = renderDialog();

    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "Rae Kim" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("option", { name: "Mia Ko" }),
    ).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Reviewer"), "8");
    await user.click(screen.getByRole("button", { name: "Send for approval" }));

    await waitFor(() =>
      expect(requestParticipantWithdrawal).toHaveBeenCalledWith(7, 3104, {
        reviewerId: 8,
        reason: "",
      }),
    );
    expect(toast.success).toHaveBeenCalledWith("Sent for approval.");
    expect(onSent).toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("shows the server's refusal and stays open", async () => {
    const user = userEvent.setup();
    requestParticipantWithdrawal.mockRejectedValue({
      response: { data: { message: "This is already waiting for approval." } },
    });
    const { onOpenChange, onSent } = renderDialog();

    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "Rae Kim" }),
      ).toBeInTheDocument(),
    );
    await user.selectOptions(screen.getByLabelText("Reviewer"), "8");
    await user.click(screen.getByRole("button", { name: "Send for approval" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "This is already waiting for approval.",
      ),
    );
    expect(onSent).not.toHaveBeenCalled();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
    expect(screen.getByLabelText("Reviewer")).toHaveValue("8");
  });

  it("says what is already waiting on a decision", () => {
    renderDialog({
      pendingRequests: [{ requestId: 41, action: "withdraw_participant" }],
    });

    expect(
      screen.getByText(/Already waiting on a decision: Withdrawal from round/),
    ).toBeInTheDocument();
  });

  it("offers a choice once there is more than one type", async () => {
    const user = userEvent.setup();
    const flag = {
      key: "flag_participant",
      label: "Raise a red flag",
      consequences: () => "A red flag goes on their record.",
      isAvailable: () => true,
      raise: vi.fn(() => Promise.resolve({ data: {} })),
    };
    renderDialog({ types: [statusRequestType("withdraw_participant"), flag] });

    const select = screen.getByLabelText("What are you asking for");
    await user.selectOptions(select, "flag_participant");

    expect(
      screen.getByText("A red flag goes on their record."),
    ).toBeInTheDocument();
  });

  it("picks the only pair for a no show by itself and sends it", async () => {
    const user = userEvent.setup();
    renderDialog({
      types: [statusRequestType("mark_no_show")],
      pairs: [pairWith(80, "Ann")],
    });

    expect(screen.getByLabelText("Which pair")).toHaveValue("80");
    expect(
      screen.getByText(/It cannot be undone. They are not told./),
    ).toBeInTheDocument();
    await pickReviewerAndSend(user);

    await waitFor(() =>
      expect(requestParticipantMark).toHaveBeenCalledWith(7, 3104, {
        tag: "no_show",
        pairId: 80,
        reviewerId: 8,
        reason: "",
      }),
    );
  });

  it("makes a mentor with two pairs pick one, and marks the ended one", async () => {
    const user = userEvent.setup();
    renderDialog({
      types: [statusRequestType("mark_no_show")],
      pairs: [pairWith(80, "Ann"), pairWith(81, "Eve", false)],
    });

    const which = screen.getByLabelText("Which pair");
    expect(which).toHaveValue("");
    expect(
      screen.getByRole("option", { name: "Eve Lee (ended)" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "Rae Kim" }),
      ).toBeInTheDocument(),
    );
    await user.selectOptions(screen.getByLabelText("Reviewer"), "8");
    expect(
      screen.getByRole("button", { name: "Send for approval" }),
    ).toBeDisabled();

    await user.selectOptions(which, "81");
    await user.click(screen.getByRole("button", { name: "Send for approval" }));

    await waitFor(() =>
      expect(requestParticipantMark).toHaveBeenCalledWith(
        7,
        3104,
        expect.objectContaining({ tag: "no_show", pairId: 81 }),
      ),
    );
  });

  it("sends a red flag about no one pair unless one is picked", async () => {
    const user = userEvent.setup();
    renderDialog({
      types: [statusRequestType("mark_red_flag")],
      pairs: [pairWith(80, "Ann")],
    });

    expect(screen.getByLabelText("Which pair")).toHaveValue("");
    expect(
      screen.getByRole("option", { name: "Not about one pair" }),
    ).toBeInTheDocument();
    await pickReviewerAndSend(user);

    await waitFor(() =>
      expect(requestParticipantMark).toHaveBeenCalledWith(7, 3104, {
        tag: "red_flag",
        pairId: null,
        reviewerId: 8,
        reason: "",
      }),
    );
  });

  it("hides the pair choice for a red flag on someone with no pairs", async () => {
    const user = userEvent.setup();
    renderDialog({
      types: [statusRequestType("mark_red_flag")],
      pairs: [],
    });

    expect(screen.queryByLabelText("Which pair")).not.toBeInTheDocument();
    await pickReviewerAndSend(user);

    await waitFor(() =>
      expect(requestParticipantMark).toHaveBeenCalledWith(7, 3104, {
        tag: "red_flag",
        pairId: null,
        reviewerId: 8,
        reason: "",
      }),
    );
  });

  it("asks no pair for a withdrawal", () => {
    renderDialog({ pairs: [pairWith(80, "Ann")] });
    expect(screen.queryByLabelText("Which pair")).not.toBeInTheDocument();
  });

  it("picks the pair again when the type changes", async () => {
    const user = userEvent.setup();
    renderDialog({
      types: [
        statusRequestType("mark_red_flag"),
        statusRequestType("mark_no_show"),
      ],
      pairs: [pairWith(80, "Ann")],
    });

    expect(screen.getByLabelText("Which pair")).toHaveValue("");
    await user.selectOptions(
      screen.getByLabelText("What are you asking for"),
      "mark_no_show",
    );
    expect(screen.getByLabelText("Which pair")).toHaveValue("80");
  });
});
