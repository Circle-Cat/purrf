import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import PostingReviewView from "@/pages/Recruiting/components/PostingReviewView";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");

const job = {
  title: "SWE",
  kind: "employment",
  description: "JD",
  formSchema: {
    questions: [{ id: "q1", type: "short_text", label: "Live question" }],
  },
  pendingFormSchema: {
    questions: [{ id: "q1", type: "short_text", label: "Pending question" }],
  },
  profileConfig: { resume: "required" },
  pendingProfileConfig: { resume: "optional" },
  pipelineConfig: { stages: [{ stage: "tech", rounds: 1 }] },
  pendingPipelineConfig: { stages: [{ stage: "board_review", rounds: 1 }] },
};

describe("PostingReviewView", () => {
  beforeEach(() => {
    api.listInterviewPool.mockResolvedValue({ data: [] });
    api.listJobOwners.mockResolvedValue({ data: [] });
  });

  it("renders the applicant view and pipeline for a non-revision review", async () => {
    render(<PostingReviewView job={job} />);
    await waitFor(() => expect(api.listInterviewPool).toHaveBeenCalled());
    expect(screen.getByLabelText("Live question")).toBeInTheDocument();
    expect(screen.getByText("1. Tech — 1 round(s)")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Live" }),
    ).not.toBeInTheDocument();
  });

  it("defaults to Pending and toggles to Live for a revision", async () => {
    render(<PostingReviewView job={job} isRevision />);
    await waitFor(() => expect(api.listInterviewPool).toHaveBeenCalled());
    expect(screen.getByLabelText("Pending question")).toBeInTheDocument();
    expect(
      screen.getByText("1. Board review — 1 round(s)"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Live" }));
    expect(screen.getByLabelText("Live question")).toBeInTheDocument();
    expect(screen.getByText("1. Tech — 1 round(s)")).toBeInTheDocument();
  });

  it("falls back to live form and pipeline when a revision omits pending fields", async () => {
    const partial = {
      title: "SWE",
      kind: "employment",
      description: "JD",
      formSchema: {
        questions: [{ id: "q1", type: "short_text", label: "Live question" }],
      },
      profileConfig: { resume: "required" },
      pipelineConfig: { stages: [{ stage: "tech", rounds: 1 }] },
      // no pendingFormSchema / pendingProfileConfig / pendingPipelineConfig
    };
    render(<PostingReviewView job={partial} isRevision />);
    await waitFor(() => expect(api.listInterviewPool).toHaveBeenCalled());
    // Pending is the default view; with no pending fields it shows live content.
    expect(screen.getByLabelText("Live question")).toBeInTheDocument();
    expect(screen.getByText("1. Tech — 1 round(s)")).toBeInTheDocument();
  });

  it("shows resolved owner/assignee names in the pipeline", async () => {
    api.listJobOwners.mockResolvedValue({
      data: [{ userId: 42, name: "Bo", email: "bo@x.com" }],
    });
    api.listInterviewPool.mockResolvedValue({
      data: [{ userId: 7, name: "Ann", email: "ann@x.com" }],
    });
    const ownerJob = {
      ...job,
      pipelineConfig: {
        ownerId: 42,
        stages: [{ stage: "tech", rounds: 1, defaultAssigneeId: 7 }],
      },
    };
    render(<PostingReviewView job={ownerJob} />);
    expect(await screen.findByText("Owner: Bo (#42)")).toBeInTheDocument();
    expect(screen.getByText("Assignee Ann (#7)")).toBeInTheDocument();
  });
});
