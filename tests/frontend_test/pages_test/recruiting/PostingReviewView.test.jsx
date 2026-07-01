import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PostingReviewView from "@/pages/Recruiting/components/PostingReviewView";

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
  it("renders the applicant view and pipeline for a non-revision review", () => {
    render(<PostingReviewView job={job} />);
    expect(screen.getByLabelText("Live question")).toBeInTheDocument();
    expect(screen.getByText("1. Tech — 1 round(s)")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Live" }),
    ).not.toBeInTheDocument();
  });

  it("defaults to Pending and toggles to Live for a revision", () => {
    render(<PostingReviewView job={job} isRevision />);
    expect(screen.getByLabelText("Pending question")).toBeInTheDocument();
    expect(
      screen.getByText("1. Board review — 1 round(s)"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Live" }));
    expect(screen.getByLabelText("Live question")).toBeInTheDocument();
    expect(screen.getByText("1. Tech — 1 round(s)")).toBeInTheDocument();
  });
});
