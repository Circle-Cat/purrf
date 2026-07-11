import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PostingConfigSummary from "@/pages/Recruiting/components/PostingConfigSummary";

describe("PostingConfigSummary", () => {
  it("lists pipeline stages with their configured rounds", () => {
    render(
      <PostingConfigSummary
        job={{
          pipelineConfig: {
            ownerIds: [2],
            stages: [
              { stage: "recruiter_screening", rounds: 1 },
              { stage: "tech", rounds: 2 },
            ],
          },
          screenRules: { rules: [] },
          profileConfig: { resume: "required" },
        }}
      />,
    );

    expect(screen.getByText(/Recruiter screening/)).toBeInTheDocument();
    expect(screen.getByText(/^Tech/)).toBeInTheDocument();
    expect(screen.getByText(/2 rounds/)).toBeInTheDocument();
  });

  it("renders a placeholder when no pipeline is configured yet", () => {
    render(<PostingConfigSummary job={{ pipelineConfig: null }} />);

    expect(screen.getByText(/No pipeline configured yet/)).toBeInTheDocument();
  });
});
