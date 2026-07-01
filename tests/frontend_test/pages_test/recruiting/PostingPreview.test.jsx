import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PostingPreview from "@/pages/Recruiting/components/PostingPreview";

const baseJob = {
  id: 1,
  title: "SWE Intern",
  kind: "employment",
  description: "A great role.",
  status: "pending_review",
  pipelineConfig: { stages: [{ stage: "tech", rounds: 1 }] },
  formSchema: {
    questions: [{ id: "q1", type: "short_text", label: "Full name" }],
  },
  pendingFormSchema: null,
};

describe("PostingPreview", () => {
  it("renders title and description", () => {
    render(<PostingPreview open={true} job={baseJob} onOpenChange={vi.fn()} />);
    expect(
      screen.getByRole("heading", { name: "SWE Intern" }),
    ).toBeInTheDocument();
    expect(screen.getByText("A great role.")).toBeInTheDocument();
  });

  it("renders the applicant form and pipeline, not JSON", () => {
    render(<PostingPreview open={true} job={baseJob} onOpenChange={vi.fn()} />);
    expect(screen.getByLabelText("Full name")).toBeInTheDocument();
    expect(screen.getByText("1. Tech — 1 round(s)")).toBeInTheDocument();
    expect(document.querySelector("pre")).toBeNull();
  });

  it("does NOT show the Pending|Live toggle for pending_review status", () => {
    render(<PostingPreview open={true} job={baseJob} onOpenChange={vi.fn()} />);
    expect(
      screen.queryByRole("button", { name: "Live" }),
    ).not.toBeInTheDocument();
  });

  it("shows a Pending|Live toggle for published_pending_revision", () => {
    const job = {
      ...baseJob,
      status: "published_pending_revision",
      pendingFormSchema: {
        questions: [{ id: "q1", type: "short_text", label: "Pending name" }],
      },
    };
    render(<PostingPreview open={true} job={job} onOpenChange={vi.fn()} />);
    expect(screen.getByLabelText("Pending name")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Live" }));
    expect(screen.getByLabelText("Full name")).toBeInTheDocument();
  });

  it("Close button calls onOpenChange(false)", () => {
    const onOpenChange = vi.fn();
    render(
      <PostingPreview open={true} job={baseJob} onOpenChange={onOpenChange} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("renders nothing when job is null", () => {
    const { container } = render(
      <PostingPreview open={true} job={null} onOpenChange={vi.fn()} />,
    );
    expect(container.querySelector("[data-slot='dialog-title']")).toBeNull();
  });

  it("does not show rejection comment block even when lastRejectComment is set", () => {
    const job = { ...baseJob, lastRejectComment: "needs work" };
    render(<PostingPreview open={true} job={job} onOpenChange={vi.fn()} />);
    expect(screen.queryByText("Rejection comment")).not.toBeInTheDocument();
    expect(screen.queryByText("needs work")).not.toBeInTheDocument();
  });
});
