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

import { beforeEach, afterEach } from "vitest";

describe("ApplicantCard cold-freeze countdown", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 6, 22)); // 2026-07-22 local
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a countdown when the thaw date is still in the future", () => {
    render(
      <ApplicantCard
        card={{
          ...baseCard,
          tags: { cold_freeze: { thaw_date: "2026-07-27" } }, // 5 days out
          isBlocked: false,
        }}
        showStatus={false}
        onOpen={vi.fn()}
      />,
    );
    expect(screen.getByText("Cold freeze · 5 days left")).toBeInTheDocument();
  });

  it("uses the singular form when exactly one day remains", () => {
    render(
      <ApplicantCard
        card={{
          ...baseCard,
          tags: { cold_freeze: { thaw_date: "2026-07-23" } }, // 1 day out
          isBlocked: false,
        }}
        showStatus={false}
        onOpen={vi.fn()}
      />,
    );
    expect(screen.getByText("Cold freeze · 1 day left")).toBeInTheDocument();
  });

  it("hides the chip once the thaw date is today or past", () => {
    render(
      <ApplicantCard
        card={{
          ...baseCard,
          tags: { cold_freeze: { thaw_date: "2026-07-22" } }, // today
          isBlocked: false,
        }}
        showStatus={false}
        onOpen={vi.fn()}
      />,
    );
    expect(screen.queryByText(/Cold freeze/)).not.toBeInTheDocument();
  });

  it("still renders the blacklist chip when an expired cold-freeze is hidden", () => {
    render(
      <ApplicantCard
        card={{
          ...baseCard,
          tags: { cold_freeze: { thaw_date: "2026-01-01" }, blacklisted: true },
          isBlocked: true,
        }}
        showStatus={false}
        onOpen={vi.fn()}
      />,
    );
    expect(screen.queryByText(/Cold freeze/)).not.toBeInTheDocument();
    expect(screen.getByText("Blacklisted")).toBeInTheDocument();
  });
});
