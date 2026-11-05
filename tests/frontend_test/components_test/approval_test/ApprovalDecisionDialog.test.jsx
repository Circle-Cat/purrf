import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import ApprovalDecisionDialog from "@/components/approval/ApprovalDecisionDialog";

const renderDialog = (decision) => {
  const onConfirm = vi.fn();
  render(
    <ApprovalDecisionDialog
      open
      onOpenChange={vi.fn()}
      decision={decision}
      title="Decide"
      description="What it does."
      onConfirm={onConfirm}
    />,
  );
  return onConfirm;
};

describe("ApprovalDecisionDialog", () => {
  it("rejects only with a reason, sent trimmed", async () => {
    const user = userEvent.setup();
    const onConfirm = renderDialog("reject");

    const reject = screen.getByRole("button", { name: "Reject" });
    expect(reject).toBeDisabled();
    await user.type(screen.getByLabelText("Reason"), " Mentor away ");
    await user.click(reject);

    expect(onConfirm).toHaveBeenCalledWith("Mentor away");
  });

  it("approves on a second click with no reason", async () => {
    const user = userEvent.setup();
    const onConfirm = renderDialog("approve");

    expect(screen.queryByLabelText("Reason")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve" }));

    expect(onConfirm).toHaveBeenCalledWith("");
  });
});
