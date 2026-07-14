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
    expect(screen.getByText(/Tech/)).toBeInTheDocument();
    expect(screen.getByText(/2 round\(s\)/)).toBeInTheDocument();
  });

  it("renders a placeholder when no pipeline is configured yet", () => {
    render(<PostingConfigSummary job={{ pipelineConfig: null }} />);

    expect(screen.getByText(/No stages configured/)).toBeInTheDocument();
  });

  it("resolves a stage's default assignee to a name via the interview pool", () => {
    render(
      <PostingConfigSummary
        job={{
          pipelineConfig: {
            ownerIds: [2],
            stages: [{ stage: "tech", rounds: 1, defaultAssigneeId: 7 }],
          },
          screenRules: { rules: [] },
          profileConfig: {},
        }}
        interviewPool={[{ userId: 7, name: "Ann", email: "ann@x.com" }]}
        jobOwners={[{ userId: 2, name: "Bo", email: "bo@x.com" }]}
      />,
    );

    expect(screen.getByText("Assignee Ann (#7)")).toBeInTheDocument();
    expect(screen.getByText("Managed by: Bo (#2)")).toBeInTheDocument();
  });

  it("describes an answer screen rule with the question's label and chosen value", () => {
    render(
      <PostingConfigSummary
        job={{
          pipelineConfig: null,
          formSchema: {
            questions: [
              { id: "q1", type: "single_choice", label: "Work authorized?" },
            ],
          },
          screenRules: {
            rules: [
              {
                id: "r1",
                condition: {
                  source: "answer",
                  operator: "equals",
                  questionId: "q1",
                  value: "No",
                },
                action: "reject",
              },
            ],
          },
          profileConfig: {},
        }}
      />,
    );

    expect(
      screen.getByText('Reject if answer to "Work authorized?" is "No"'),
    ).toBeInTheDocument();
  });

  it("describes an email-domain screen rule in plain language", () => {
    render(
      <PostingConfigSummary
        job={{
          pipelineConfig: null,
          screenRules: {
            rules: [
              {
                id: "r1",
                condition: {
                  source: "email_domain",
                  operator: "not_in",
                  value: ["google.com", "circlecat.org"],
                },
                action: "qualify",
              },
            ],
          },
          profileConfig: {},
        }}
      />,
    );

    expect(
      screen.getByText(
        "Qualify if email domain is not one of google.com, circlecat.org",
      ),
    ).toBeInTheDocument();
  });

  it("reads the work-experience requirement from workExperience, not experience", () => {
    render(
      <PostingConfigSummary
        job={{
          pipelineConfig: null,
          screenRules: { rules: [] },
          profileConfig: { workExperience: "required" },
        }}
      />,
    );

    expect(screen.getByText("Work experience: Required")).toBeInTheDocument();
  });

  it("shows Kind, Mentorship role, and Cooldown days above the pipeline summary", () => {
    render(
      <PostingConfigSummary
        job={{
          kind: "activity",
          mentorshipRole: "mentor",
          cooldownDays: 30,
          pipelineConfig: null,
          screenRules: null,
          profileConfig: null,
        }}
      />,
    );

    expect(screen.getByText("Kind: Activity")).toBeInTheDocument();
    expect(screen.getByText("Mentorship role: Mentor")).toBeInTheDocument();
    expect(screen.getByText("Cooldown days: 30")).toBeInTheDocument();
  });

  it("hides Mentorship role for an employment kind posting", () => {
    const baseJob = {
      kind: "activity",
      mentorshipRole: "mentor",
      cooldownDays: 30,
      pipelineConfig: null,
      screenRules: null,
      profileConfig: null,
    };

    render(
      <PostingConfigSummary
        job={{ ...baseJob, kind: "employment", mentorshipRole: null }}
      />,
    );

    expect(screen.getByText("Kind: Employment")).toBeInTheDocument();
    expect(screen.queryByText(/Mentorship role/)).not.toBeInTheDocument();
  });

  it("shows an em dash for a null cooldownDays", () => {
    const baseJob = {
      kind: "activity",
      mentorshipRole: "mentor",
      cooldownDays: 30,
      pipelineConfig: null,
      screenRules: null,
      profileConfig: null,
    };

    render(<PostingConfigSummary job={{ ...baseJob, cooldownDays: null }} />);

    expect(screen.getByText("Cooldown days: —")).toBeInTheDocument();
  });
});
