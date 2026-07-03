import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import * as api from "@/api/recruitingApi";
import PostingPreviewPage from "@/pages/Recruiting/components/PostingPreviewPage";

vi.mock("@/api/recruitingApi");

const job = {
  id: 1,
  title: "SWE Intern",
  kind: "employment",
  description: "A great role.",
  status: "pending_review",
  formSchema: {
    questions: [{ id: "q1", type: "short_text", label: "Full name" }],
  },
  pipelineConfig: { stages: [{ stage: "tech", rounds: 1 }] },
};

beforeEach(() => {
  vi.clearAllMocks();
  api.listInterviewPool.mockResolvedValue({ data: [] });
  api.listJobOwners.mockResolvedValue({ data: [] });
});

describe("PostingPreviewPage", () => {
  it("renders the applicant view and pipeline read-only, with a Back button", async () => {
    render(<PostingPreviewPage job={job} onBack={() => {}} />);
    await waitFor(() => expect(api.listInterviewPool).toHaveBeenCalled());
    expect(
      screen.getByRole("heading", { name: "SWE Intern" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Full name")).toBeInTheDocument();
    expect(screen.getByText("1. Tech — 1 round(s)")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Approve" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Reject" }),
    ).not.toBeInTheDocument();
  });

  it("calls onBack when Back is clicked", async () => {
    const onBack = vi.fn();
    render(<PostingPreviewPage job={job} onBack={onBack} />);
    await waitFor(() => expect(api.listInterviewPool).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Back/ }));
    expect(onBack).toHaveBeenCalled();
  });

  it("shows a Pending|Live toggle for a published_pending_revision posting", async () => {
    const revJob = {
      ...job,
      status: "published_pending_revision",
      pendingPayload: {
        formSchema: {
          questions: [{ id: "q1", type: "short_text", label: "Pending name" }],
        },
      },
    };
    render(<PostingPreviewPage job={revJob} onBack={() => {}} />);
    await waitFor(() => expect(api.listInterviewPool).toHaveBeenCalled());
    expect(screen.getByLabelText("Pending name")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Live" }));
    expect(screen.getByLabelText("Full name")).toBeInTheDocument();
  });
});
