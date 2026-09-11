import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ReassignReviewerDialog from "@/pages/Recruiting/components/ReassignReviewerDialog";

const approvers = [
  { userId: 1, name: "Me", email: "me@x.com" },
  { userId: 2, name: "Bob", email: "bob@x.com" },
  { userId: 3, name: "Cara", email: "cara@x.com" },
];

const renderDialog = (props = {}) =>
  render(
    <ReassignReviewerDialog
      open
      approvers={approvers}
      currentUserId={1}
      currentReviewerId={2}
      onSubmit={() => {}}
      onOpenChange={() => {}}
      {...props}
    />,
  );

describe("ReassignReviewerDialog", () => {
  it("leaves out the reviewer who has it and the submitter", () => {
    renderDialog();

    const options = [...screen.getByLabelText("Reviewer").options].map(
      (o) => o.textContent,
    );
    expect(options).toEqual(["Select a reviewer…", "Cara (cara@x.com)"]);
  });

  it("explains an empty pool rather than showing an empty picker", () => {
    // Every approver is either the submitter or the reviewer who has it, so
    // there is nobody left to move it to. An empty dropdown would read as a
    // malfunction rather than as a fact about the org.
    renderDialog({ approvers: approvers.slice(0, 2) });

    expect(
      screen.getByText("There is nobody else to review this posting."),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Reviewer")).not.toBeInTheDocument();
  });

  it("submits the chosen reviewer", () => {
    const onSubmit = vi.fn();
    renderDialog({ onSubmit });

    fireEvent.change(screen.getByLabelText("Reviewer"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reassign" }));

    expect(onSubmit).toHaveBeenCalledWith(3);
  });

  it("keeps Reassign disabled until somebody is chosen", () => {
    renderDialog();

    expect(screen.getByRole("button", { name: "Reassign" })).toBeDisabled();
  });

  it("says the previous reviewer is not told", () => {
    // Unlike a block request, where both reviewers hear about the handover.
    // The usual reason for reassigning is that the previous reviewer's
    // account was turned off, so mail to them would go nowhere.
    renderDialog();

    expect(
      screen.getByText(
        "Only the new reviewer is told. The posting stays where it is.",
      ),
    ).toBeInTheDocument();
  });
});
