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
  formSchema: {
    questions: [{ id: "q1", type: "short_text", label: "Your name" }],
  },
  pipelineConfig: { stages: [{ stage: "tech", rounds: 1 }] },
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
    expect(
      screen.getByRole("heading", { level: 2, name: "SWE" }),
    ).toBeInTheDocument();
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

  it("renders the applicant form and readable pipeline for a review", () => {
    render(
      <ReviewDetail
        review={review}
        job={job}
        onApprove={() => {}}
        onReject={() => {}}
        onBack={() => {}}
      />,
    );
    expect(screen.getByLabelText("Your name")).toBeInTheDocument();
    expect(screen.getByText("1. Tech — 1 round(s)")).toBeInTheDocument();
    expect(document.querySelector("pre")).toBeNull();
  });

  it("shows a Pending|Live toggle for a revision", () => {
    const revisionJob = {
      ...job,
      pendingPayload: {
        formSchema: {
          questions: [{ id: "q1", type: "short_text", label: "Pending name" }],
        },
      },
    };
    render(
      <ReviewDetail
        review={{ ...review, kind: "revision" }}
        job={revisionJob}
        onApprove={() => {}}
        onReject={() => {}}
        onBack={() => {}}
      />,
    );
    expect(screen.getByLabelText("Pending name")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Live" }));
    expect(screen.getByLabelText("Your name")).toBeInTheDocument();
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
    expect(
      screen.getByRole("heading", { level: 1, name: "SWE" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Interview pipeline")).not.toBeInTheDocument();
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
    expect(screen.queryByText("Interview pipeline")).not.toBeInTheDocument();
  });

  it("shows a Pending|Live toggle for kind=reopen when the posting has a staged edit", () => {
    const reopenJobWithEdit = {
      ...job,
      pendingPayload: {
        formSchema: {
          questions: [
            { id: "q1", type: "short_text", label: "Pending reopen name" },
          ],
        },
      },
    };
    render(
      <ReviewDetail
        review={{ ...review, kind: "reopen" }}
        job={reopenJobWithEdit}
        onApprove={() => {}}
        onReject={() => {}}
        onBack={() => {}}
      />,
    );
    expect(
      screen.getByText("Request to reopen this posting."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Pending reopen name")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Live" }));
    expect(screen.getByLabelText("Your name")).toBeInTheDocument();
  });

  it("deciding disables both Approve and Reject, to prevent a double-submit", () => {
    render(
      <ReviewDetail
        review={review}
        job={job}
        deciding
        onApprove={() => {}}
        onReject={() => {}}
        onBack={() => {}}
      />,
    );
    // A non-empty comment would otherwise enable Reject -- confirm `deciding`
    // overrides that, not just coincides with the empty-comment disable.
    fireEvent.change(screen.getByLabelText("Rejection comment"), {
      target: { value: "fix it" },
    });
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
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
