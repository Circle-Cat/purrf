import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PostingPreview from "@/pages/Recruiting/components/PostingPreview";

const baseJob = {
  id: 1,
  title: "SWE Intern",
  kind: "employment",
  description: "A great role.",
  status: "pending_review",
  pipelineConfig: { stages: ["screen"] },
  formSchema: { fields: ["name"] },
  pendingFormSchema: null,
};

describe("PostingPreview", () => {
  it("renders title and description", () => {
    render(<PostingPreview open={true} job={baseJob} onOpenChange={vi.fn()} />);
    expect(screen.getByText("SWE Intern")).toBeInTheDocument();
    expect(screen.getByText("A great role.")).toBeInTheDocument();
  });

  it("renders formSchema as pretty-printed JSON", () => {
    render(<PostingPreview open={true} job={baseJob} onOpenChange={vi.fn()} />);
    const expected = JSON.stringify(baseJob.formSchema, null, 2);
    const pres = document.querySelectorAll("pre");
    const formPre = Array.from(pres).find((p) => p.textContent === expected);
    expect(formPre).toBeTruthy();
  });

  it("does NOT show pending block for pending_review status", () => {
    render(<PostingPreview open={true} job={baseJob} onOpenChange={vi.fn()} />);
    expect(screen.queryByText("Pending revision")).not.toBeInTheDocument();
  });

  it("shows pending block for published_pending_revision", () => {
    const job = {
      ...baseJob,
      status: "published_pending_revision",
      pendingFormSchema: { fields: ["name", "email"] },
    };
    render(<PostingPreview open={true} job={job} onOpenChange={vi.fn()} />);
    expect(screen.getByText("Pending revision")).toBeInTheDocument();
    const expectedPending = JSON.stringify(job.pendingFormSchema, null, 2);
    const pres = document.querySelectorAll("pre");
    const pendingPre = Array.from(pres).find(
      (p) => p.textContent === expectedPending,
    );
    expect(pendingPre).toBeTruthy();
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
