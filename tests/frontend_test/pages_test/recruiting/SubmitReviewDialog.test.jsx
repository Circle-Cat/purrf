import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SubmitReviewDialog from "@/pages/Recruiting/components/SubmitReviewDialog";

const approvers = [
  { userId: 1, name: "Me", email: "me@x.com" },
  { userId: 2, name: "Bob", email: "bob@x.com" },
  { userId: 3, name: "Cara", email: "cara@x.com" },
];

describe("SubmitReviewDialog", () => {
  it("renders default title 'Submit for review' when no title prop passed", () => {
    render(
      <SubmitReviewDialog
        open
        approvers={approvers}
        currentUserId={1}
        onSubmit={() => {}}
        onOpenChange={() => {}}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Submit for review" }),
    ).toBeInTheDocument();
  });

  it("renders custom title when title prop is passed", () => {
    render(
      <SubmitReviewDialog
        open
        approvers={approvers}
        currentUserId={1}
        title="Request close"
        onSubmit={() => {}}
        onOpenChange={() => {}}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Request close" }),
    ).toBeInTheDocument();
  });
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
    // Total pool = 1 (below MIN_APPROVER_POOL=2); gate uses total, not self-excluded count.
    render(
      <SubmitReviewDialog
        open
        approvers={[{ userId: 2, name: "Bob", email: "bob@x.com" }]}
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

  it("disables Submit and ignores clicks while submitting is true", () => {
    const onSubmit = vi.fn();
    render(
      <SubmitReviewDialog
        open
        approvers={approvers}
        currentUserId={1}
        submitting
        onSubmit={onSubmit}
        onOpenChange={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("Reviewer"), {
      target: { value: "2" },
    });
    const submitButton = screen.getByRole("button", { name: "Submit" });
    expect(submitButton).toBeDisabled();
    fireEvent.click(submitButton);
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
