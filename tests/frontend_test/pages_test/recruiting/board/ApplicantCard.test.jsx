import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ApplicantCard from "@/pages/Recruiting/board/ApplicantCard";

const baseCard = {
  id: 1,
  applicantName: "Ada Lovelace",
  applicantEmail: "ada@example.com",
  stage: "recruiter_screening",
  subStatus: null,
  tags: null,
  appliedAt: "2026-06-01T00:00:00Z",
  reviewerName: null,
};

describe("ApplicantCard blacklist tag", () => {
  it("shows a red Blacklisted badge when the applicant is still currently blocked", () => {
    render(
      <ApplicantCard
        card={{
          ...baseCard,
          tags: { blacklisted: true },
          isBlocked: true,
        }}
        showStatus={false}
        onOpen={vi.fn()}
      />,
    );
    expect(screen.getByText("Blacklisted")).toBeInTheDocument();
    expect(screen.queryByText("Blacklist Lifted")).not.toBeInTheDocument();
  });

  it("shows a gray Blacklist Lifted badge once the user has been unblocked", () => {
    render(
      <ApplicantCard
        card={{
          ...baseCard,
          tags: { blacklisted: true },
          isBlocked: false,
        }}
        showStatus={false}
        onOpen={vi.fn()}
      />,
    );
    expect(screen.getByText("Blacklist Lifted")).toBeInTheDocument();
    expect(screen.queryByText("Blacklisted")).not.toBeInTheDocument();
  });

  it("shows neither badge when the application was never blacklisted", () => {
    render(
      <ApplicantCard card={baseCard} showStatus={false} onOpen={vi.fn()} />,
    );
    expect(screen.queryByText("Blacklisted")).not.toBeInTheDocument();
    expect(screen.queryByText("Blacklist Lifted")).not.toBeInTheDocument();
  });
});

describe("ApplicantCard reviewer", () => {
  it("shows the reviewer name in accent color when present", () => {
    render(
      <ApplicantCard
        card={{ ...baseCard, reviewerName: "Ivan Interviewer" }}
        showStatus
        onOpen={vi.fn()}
      />,
    );

    const reviewer = screen.getByText("Reviewer: Ivan Interviewer");
    expect(reviewer).toBeInTheDocument();
    expect(reviewer.className).toContain("text-blue-600");
  });

  it("shows N/A in muted color when no reviewer is assigned", () => {
    render(<ApplicantCard card={baseCard} showStatus onOpen={vi.fn()} />);

    const reviewer = screen.getByText("Reviewer: N/A");
    expect(reviewer).toBeInTheDocument();
    expect(reviewer.className).toContain("text-slate-400");
  });

  it("hides the reviewer line entirely for a non-interview stage", () => {
    render(
      <ApplicantCard
        card={{ ...baseCard, stage: "hired", reviewerName: null }}
        showStatus={false}
        onOpen={vi.fn()}
      />,
    );

    expect(screen.queryByText(/^Reviewer:/)).not.toBeInTheDocument();
  });
});
