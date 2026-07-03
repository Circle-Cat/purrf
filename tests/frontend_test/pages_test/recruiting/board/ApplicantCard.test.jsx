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
