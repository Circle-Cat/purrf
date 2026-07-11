import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PostingConfigSummary from "@/pages/Recruiting/components/PostingConfigSummary";

describe("PostingConfigSummary", () => {
  const baseJob = {
    kind: "activity",
    mentorshipRole: "mentor",
    cooldownDays: 30,
    pipelineConfig: null,
    screenRules: null,
    profileConfig: null,
  };

  it("shows Kind, Mentorship role, and Cooldown days above the pipeline summary", () => {
    render(<PostingConfigSummary job={baseJob} />);

    expect(screen.getByText("Kind: Activity")).toBeInTheDocument();
    expect(screen.getByText("Mentorship role: Mentor")).toBeInTheDocument();
    expect(screen.getByText("Cooldown days: 30")).toBeInTheDocument();
  });

  it("hides Mentorship role for an employment kind posting", () => {
    render(
      <PostingConfigSummary
        job={{ ...baseJob, kind: "employment", mentorshipRole: null }}
      />,
    );

    expect(screen.getByText("Kind: Employment")).toBeInTheDocument();
    expect(screen.queryByText(/Mentorship role/)).not.toBeInTheDocument();
  });

  it("shows an em dash for a null cooldownDays", () => {
    render(<PostingConfigSummary job={{ ...baseJob, cooldownDays: null }} />);

    expect(screen.getByText("Cooldown days: —")).toBeInTheDocument();
  });
});
