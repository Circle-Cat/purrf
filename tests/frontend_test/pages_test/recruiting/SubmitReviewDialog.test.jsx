import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SubmitReviewDialog from "@/pages/Recruiting/components/SubmitReviewDialog";

const approvers = [
  { userId: 1, name: "Me", email: "me@x.com" },
  { userId: 2, name: "Bob", email: "bob@x.com" },
  { userId: 3, name: "Cara", email: "cara@x.com" },
];

describe("SubmitReviewDialog", () => {
  it("excludes the current user from the reviewer options", () => {
    render(
      <SubmitReviewDialog
        open
        approvers={approvers}
        currentUserId={1}
        onSubmit={() => {}}
        onOpenChange={() => {}}
      />,
    );
    const select = screen.getByLabelText("Reviewer");
    expect(select).not.toHaveTextContent("Me");
    expect(screen.getByRole("option", { name: /Bob/ })).toBeInTheDocument();
  });

  it("disables submit when fewer than 2 approvers are available", () => {
    render(
      <SubmitReviewDialog
        open
        approvers={[approvers[0], approvers[1]]}
        currentUserId={1}
        onSubmit={() => {}}
        onOpenChange={() => {}}
      />,
    );
    expect(screen.getByText(/at least 2 approvers/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });

  it("submits the chosen reviewer and message", () => {
    const onSubmit = vi.fn();
    render(
      <SubmitReviewDialog
        open
        approvers={approvers}
        currentUserId={1}
        onSubmit={onSubmit}
        onOpenChange={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("Reviewer"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "pls" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(onSubmit).toHaveBeenCalledWith({ reviewerId: 2, message: "pls" });
  });
});
