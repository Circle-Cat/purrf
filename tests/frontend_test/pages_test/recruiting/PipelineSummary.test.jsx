import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PipelineSummary from "@/pages/Recruiting/components/PipelineSummary";

describe("PipelineSummary", () => {
  it("renders ordered stages with rounds and tags", () => {
    render(
      <PipelineSummary
        pipelineConfig={{
          ownerId: 42,
          stages: [
            {
              stage: "recruiter_screening",
              rounds: 1,
              referralSkippable: true,
            },
            {
              stage: "tech",
              rounds: 2,
              referralSkippable: false,
              defaultAssigneeId: 7,
            },
          ],
        }}
      />,
    );
    expect(
      screen.getByText("1. Recruiter screening — 1 round(s)"),
    ).toBeInTheDocument();
    expect(screen.getByText("2. Tech — 2 round(s)")).toBeInTheDocument();
    expect(screen.getByText("Referral-skippable")).toBeInTheDocument();
    expect(screen.getByText("Assignee #7")).toBeInTheDocument();
    expect(screen.getByText("Owner: #42")).toBeInTheDocument();
  });

  it("shows an empty note when there are no stages", () => {
    render(<PipelineSummary pipelineConfig={{ stages: [] }} />);
    expect(screen.getByText("No stages configured.")).toBeInTheDocument();
  });
});
