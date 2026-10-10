import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import ApprovalRequestDialog from "@/components/approval/ApprovalRequestDialog";

const REVIEWERS = [
  { userId: 8, name: "Rae Kim" },
  { userId: 12, name: "Sam Oyelaran" },
];

const renderDialog = (props = {}) => {
  const onConfirm = vi.fn();
  render(
    <ApprovalRequestDialog
      open
      onOpenChange={vi.fn()}
      title="Request publishing"
      description="Sent to a reviewer."
      reviewers={REVIEWERS}
      confirmLabel="Send request"
      onConfirm={onConfirm}
      {...props}
    />,
  );
  return onConfirm;
};

describe("ApprovalRequestDialog", () => {
  it("sends the chosen reviewer and the trimmed reason", async () => {
    const user = userEvent.setup();
    const onConfirm = renderDialog({ askReason: true });

    const send = screen.getByRole("button", { name: "Send request" });
    expect(send).toBeDisabled();
    await user.selectOptions(screen.getByLabelText("Reviewer"), "8");
    await user.type(
      screen.getByLabelText("Reason (optional)"),
      "  Reviewed every pair ",
    );
    await user.click(send);

    expect(onConfirm).toHaveBeenCalledWith({
      reviewerId: 8,
      reason: "Reviewed every pair",
    });
  });

  it("sends without a reason, which is always optional", async () => {
    const user = userEvent.setup();
    const onConfirm = renderDialog({ askReason: true });

    await user.selectOptions(screen.getByLabelText("Reviewer"), "12");
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(onConfirm).toHaveBeenCalledWith({ reviewerId: 12, reason: "" });
  });

  it("keeps Send disabled while the caller says something is missing", async () => {
    const user = userEvent.setup();
    renderDialog({ canConfirm: false });

    await user.selectOptions(screen.getByLabelText("Reviewer"), "8");

    expect(screen.getByRole("button", { name: "Send request" })).toBeDisabled();
  });

  it("offers no reason box unless asked to", () => {
    renderDialog();

    expect(
      screen.queryByLabelText("Reason (optional)"),
    ).not.toBeInTheDocument();
  });

  it("leaves out the people who may not review it", () => {
    renderDialog({ excludeUserIds: ["8", null] });

    expect(
      screen.getByRole("option", { name: "Sam Oyelaran" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "Rae Kim" }),
    ).not.toBeInTheDocument();
  });

  it("says so when nobody can be picked, in the caller's words", () => {
    renderDialog({
      reviewers: [],
      emptyText: "Ask for someone to hold the approve permission.",
    });

    expect(
      screen.getByText("Ask for someone to hold the approve permission."),
    ).toBeInTheDocument();
  });

  it("says so when the reviewers could not be loaded", () => {
    renderDialog({ reviewers: [], reviewersError: true });

    expect(screen.getByText(/Couldn.t load the reviewers/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Reviewer")).not.toBeInTheDocument();
  });

  it("shows what the caller adds above the picker", () => {
    renderDialog({ children: <p>2 open applications will be closed.</p> });

    expect(
      screen.getByText("2 open applications will be closed."),
    ).toBeInTheDocument();
  });

  it("labels options, hints at who is left out, and names the reason box as asked", () => {
    renderDialog({
      askReason: true,
      reasonLabel: "Message (optional)",
      reviewerHint: "You are not in this list.",
      optionLabel: (r) => `${r.name} <${r.userId}>`,
    });

    expect(
      screen.getByRole("option", { name: "Rae Kim <8>" }),
    ).toBeInTheDocument();
    expect(screen.getByText("You are not in this list.")).toBeInTheDocument();
    expect(screen.getByLabelText("Message (optional)")).toBeInTheDocument();
  });

  it("shows the caller's explanation in place of an empty picker", () => {
    renderDialog({
      reviewers: [],
      emptyContent: <p>Ask an admin to grant someone access.</p>,
    });

    expect(
      screen.getByText("Ask an admin to grant someone access."),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Reviewer")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send request" })).toBeDisabled();
  });
});
