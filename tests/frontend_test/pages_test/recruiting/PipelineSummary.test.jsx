import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PipelineSummary from "@/pages/Recruiting/components/PipelineSummary";
import {
  unresolvedPersonLabel,
  unavailablePersonLabel,
} from "@/pages/Recruiting/components/personLabel";

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
            },
            {
              stage: "tech",
              rounds: 2,
              defaultAssigneeId: 7,
            },
          ],
        }}
      />,
    );
    expect(
      screen.getByText("1. Recruiter screening — 1 session"),
    ).toBeInTheDocument();
    expect(screen.getByText("2. Tech — 2 sessions")).toBeInTheDocument();
    expect(
      screen.getByText("Assignee User 7 — unavailable"),
    ).toBeInTheDocument();
    // The "Recruiter:" prefix and this id's flagged text are separate DOM
    // nodes (the id is wrapped in its own <span> for red styling), so
    // Testing Library's default text matcher — which only concatenates an
    // element's direct text-node children — can't match the two together
    // as one string. Assert on the flagged span's own text instead; the
    // "Recruiter: Name (#id)" full-prefix case is covered by the other
    // tests below, where the resolved label is a plain sibling text node.
    expect(screen.getByText("User 42 — unavailable")).toBeInTheDocument();
  });

  it("shows an empty note when there are no stages", () => {
    render(<PipelineSummary pipelineConfig={{ stages: [] }} />);
    expect(screen.getByText("No stages configured.")).toBeInTheDocument();
  });

  it("resolves owner and assignee ids to names via the pools", () => {
    render(
      <PipelineSummary
        pipelineConfig={{
          ownerId: 42,
          stages: [{ stage: "tech", rounds: 1, defaultAssigneeId: 7 }],
        }}
        jobOwners={[{ userId: 42, name: "Bo", email: "bo@x.com" }]}
        interviewPool={[{ userId: 7, name: "Ann", email: "ann@x.com" }]}
      />,
    );
    expect(screen.getByText("Recruiter: Bo (#42)")).toBeInTheDocument();
    expect(screen.getByText("Assignee Ann (#7)")).toBeInTheDocument();
  });

  it("renders all owner names comma-separated for ownerIds", () => {
    render(
      <PipelineSummary
        pipelineConfig={{
          ownerIds: [42, 43],
          stages: [],
        }}
        jobOwners={[
          { userId: 42, name: "Bo", email: "bo@x.com" },
          { userId: 43, name: "Cy", email: "cy@x.com" },
        ]}
      />,
    );
    expect(
      screen.getByText("Recruiter: Bo (#42), Cy (#43)"),
    ).toBeInTheDocument();
  });
});

describe("unresolved person label shapes", () => {
  it("bare has no suffix; the unavailable shape does", () => {
    expect(unresolvedPersonLabel(42)).toBe("User 42");
    expect(unavailablePersonLabel(42)).toBe("User 42 — unavailable");
  });
});
