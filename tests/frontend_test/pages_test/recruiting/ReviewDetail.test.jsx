import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ReviewDetail from "@/pages/Recruiting/components/ReviewDetail";

const review = {
  reviewId: 5,
  jobId: 1,
  kind: "initial",
  submitMessage: "look",
};
const job = {
  id: 1,
  title: "SWE",
  description: "JD",
  status: "pending_review",
  formSchema: { a: 1 },
  pipelineConfig: [{ stage: "tech" }],
};

describe("ReviewDetail", () => {
  it("renders the job title and submit message", () => {
    render(
      <ReviewDetail
        review={review}
        job={job}
        onApprove={() => {}}
        onReject={() => {}}
        onBack={() => {}}
      />,
    );
    expect(screen.getByText("SWE")).toBeInTheDocument();
    expect(screen.getByText("look")).toBeInTheDocument();
  });

  it("approves via callback", () => {
    const onApprove = vi.fn();
    render(
      <ReviewDetail
        review={review}
        job={job}
        onApprove={onApprove}
        onReject={() => {}}
        onBack={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(onApprove).toHaveBeenCalled();
  });

  it("requires a comment to reject", () => {
    const onReject = vi.fn();
    render(
      <ReviewDetail
        review={review}
        job={job}
        onApprove={() => {}}
        onReject={onReject}
        onBack={() => {}}
      />,
    );
    const rejectBtn = screen.getByRole("button", { name: "Reject" });
    expect(rejectBtn).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Rejection comment"), {
      target: { value: "fix it" },
    });
    expect(rejectBtn).not.toBeDisabled();
    fireEvent.click(rejectBtn);
    expect(onReject).toHaveBeenCalledWith("fix it");
  });

  it("shows live vs pending for a revision", () => {
    render(
      <ReviewDetail
        review={{ ...review, kind: "revision" }}
        job={{
          ...job,
          status: "published_pending_revision",
          pendingFormSchema: { a: 2 },
        }}
        onApprove={() => {}}
        onReject={() => {}}
        onBack={() => {}}
      />,
    );
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("shows 'Request to close this posting.' for kind=close and hides pipeline/form blocks", () => {
    render(
      <ReviewDetail
        review={{ ...review, kind: "close" }}
        job={job}
        onApprove={() => {}}
        onReject={() => {}}
        onBack={() => {}}
      />,
    );
    expect(
      screen.getByText("Request to close this posting."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Pipeline")).not.toBeInTheDocument();
    expect(screen.queryByText("Form schema")).not.toBeInTheDocument();
  });

  it("shows 'Request to reopen this posting.' for kind=reopen and hides pipeline/form blocks", () => {
    render(
      <ReviewDetail
        review={{ ...review, kind: "reopen" }}
        job={job}
        onApprove={() => {}}
        onReject={() => {}}
        onBack={() => {}}
      />,
    );
    expect(
      screen.getByText("Request to reopen this posting."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Pipeline")).not.toBeInTheDocument();
    expect(screen.queryByText("Form schema")).not.toBeInTheDocument();
  });

  it("approve/reject still work for kind=close", () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    render(
      <ReviewDetail
        review={{ ...review, kind: "close" }}
        job={job}
        onApprove={onApprove}
        onReject={onReject}
        onBack={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(onApprove).toHaveBeenCalled();

    const rejectBtn = screen.getByRole("button", { name: "Reject" });
    expect(rejectBtn).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Rejection comment"), {
      target: { value: "no" },
    });
    expect(rejectBtn).not.toBeDisabled();
    fireEvent.click(rejectBtn);
    expect(onReject).toHaveBeenCalledWith("no");
  });
});
