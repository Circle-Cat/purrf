import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom";

import TrainingSection from "@/pages/Profile/components/TrainingSection";

const BASE_TIMESTAMPS = {
  completedTimestamp: "2023-01-15T00:00:00Z",
  deadline: "2023-02-15T00:00:00Z",
};

const TRAINING_FIXTURES = {
  single: [
    {
      id: 1,
      category: "mentorship_mentor_onboarding",
      status: "done",
      link: "https://example.com/cert",
      ...BASE_TIMESTAMPS,
    },
  ],

  statusMix: [
    {
      id: 1,
      category: "mentorship_mentor_onboarding",
      status: "done",
      link: "",
      ...BASE_TIMESTAMPS,
    },
    {
      id: 2,
      category: "mentorship_mentee_onboarding",
      status: "to_do",
      link: "",
      ...BASE_TIMESTAMPS,
    },
  ],

  withAndWithoutLink: [
    {
      id: 1,
      category: "corporate_culture_course",
      status: "done",
      link: "http://test.com",
      ...BASE_TIMESTAMPS,
    },
    {
      id: 2,
      category: "residency_program_onboarding",
      status: "done",
      link: null,
      ...BASE_TIMESTAMPS,
    },
  ],

  unknownCategory: [
    {
      id: 1,
      category: "unmapped_future_category",
      status: "done",
      link: "",
      ...BASE_TIMESTAMPS,
    },
  ],
};

describe("TrainingSection Component", () => {
  it("renders the header correctly", () => {
    render(<TrainingSection list={[]} />);

    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent(
      "Training",
    );
  });

  it("renders empty state when list is empty or null", () => {
    const { rerender } = render(<TrainingSection list={[]} />);
    expect(screen.getByText("No training records found.")).toBeInTheDocument();

    rerender(<TrainingSection list={null} />);
    expect(screen.getByText("No training records found.")).toBeInTheDocument();
  });

  it("renders the friendly category label and the actual day for each timestamp", () => {
    render(<TrainingSection list={TRAINING_FIXTURES.single} />);

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(
      screen.getByText("Mentorship Mentor Onboarding"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("mentorship_mentor_onboarding"),
    ).not.toBeInTheDocument();

    // Full calendar day, not just month/year. Forced en-US + UTC so the
    // assertion is deterministic regardless of test-runner locale.
    expect(screen.getByText("Jan 15, 2023")).toBeInTheDocument();
    expect(screen.getByText("Feb 15, 2023")).toBeInTheDocument();
  });

  it("falls back to the raw category string when label mapping is missing", () => {
    render(<TrainingSection list={TRAINING_FIXTURES.unknownCategory} />);

    expect(screen.getByText("unmapped_future_category")).toBeInTheDocument();
  });

  it("highlights an incomplete mentorship onboarding row", () => {
    render(
      <TrainingSection
        list={[
          {
            id: 1,
            category: "mentorship_mentor_onboarding",
            status: "to_do",
            link: "",
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    expect(screen.getByTestId("training-row-required")).toHaveClass(
      "bg-accent",
    );
  });

  it("does not highlight a completed onboarding row", () => {
    render(
      <TrainingSection
        list={[
          {
            id: 1,
            category: "mentorship_mentee_onboarding",
            status: "done",
            link: "",
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    expect(
      screen.queryByTestId("training-row-required"),
    ).not.toBeInTheDocument();
  });

  it("does not highlight an incomplete non-onboarding training", () => {
    render(
      <TrainingSection
        list={[
          {
            id: 1,
            category: "residency_program_onboarding",
            status: "to_do",
            link: "",
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    expect(
      screen.queryByTestId("training-row-required"),
    ).not.toBeInTheDocument();
  });

  it("renders status correctly based on status value", () => {
    render(<TrainingSection list={TRAINING_FIXTURES.statusMix} />);

    const completedTag = screen.getByText("Completed");
    expect(completedTag).toBeInTheDocument();
    expect(completedTag).toHaveClass("bg-accent", "text-primary");

    const pendingTag = screen.getByText("Not Completed");
    expect(pendingTag).toBeInTheDocument();
    expect(pendingTag).toHaveClass("bg-primary", "text-primary-foreground");
  });

  it("renders the timestamp in the user's profile timezone when provided", () => {
    // 2023-01-15T00:00:00Z is midnight UTC, which in Los Angeles
    // (UTC-8) is still 2023-01-14 16:00 → calendar day shifts back to
    // Jan 14.
    render(
      <TrainingSection
        list={[
          {
            id: 1,
            category: "corporate_culture_course",
            status: "done",
            link: "",
            completedTimestamp: "2023-01-15T00:00:00Z",
            deadline: "2023-02-15T00:00:00Z",
          },
        ]}
        timezone="America/Los_Angeles"
      />,
    );

    expect(screen.getByText("Jan 14, 2023")).toBeInTheDocument();
    expect(screen.getByText("Feb 14, 2023")).toBeInTheDocument();
  });

  it("falls back to UTC when no timezone prop is provided", () => {
    // Same input as above; without a timezone the same UTC midnight
    // displays as Jan 15 (the stored calendar day).
    render(<TrainingSection list={TRAINING_FIXTURES.single} />);

    expect(screen.getByText("Jan 15, 2023")).toBeInTheDocument();
    expect(screen.getByText("Feb 15, 2023")).toBeInTheDocument();
  });

  it('renders "-" for the 1970 sentinel completedTimestamp', () => {
    render(
      <TrainingSection
        list={[
          {
            id: 1,
            category: "mentorship_mentor_onboarding",
            status: "to_do",
            // Non-empty so the link cell renders "View Link" instead of "-",
            // letting us assert exactly one "-" from the sentinel cell.
            link: "https://example.com/cert",
            completedTimestamp: "1970-01-01T00:00:00Z",
            deadline: "2026-05-18T06:59:00Z",
          },
        ]}
      />,
    );

    // Sentinel completed_timestamp → "-"; real deadline → actual day.
    expect(screen.getByText("-")).toBeInTheDocument();
    expect(screen.getByText("May 18, 2026")).toBeInTheDocument();
  });

  it('renders "-" when timestamps are null or invalid', () => {
    render(
      <TrainingSection
        list={[
          {
            id: 1,
            category: "corporate_culture_course",
            status: "done",
            link: "",
            completedTimestamp: null,
            deadline: "not-a-date",
          },
        ]}
      />,
    );

    expect(screen.getAllByText("-").length).toBeGreaterThanOrEqual(2);
  });

  it("renders links correctly based on link value", () => {
    render(<TrainingSection list={TRAINING_FIXTURES.withAndWithoutLink} />);

    const link = screen.getByRole("link", { name: /view link/i });
    expect(link).toHaveAttribute("href", "http://test.com");
    expect(link).toHaveAttribute("target", "_blank");

    const noLinkRow = screen
      .getByText("Residency Program Onboarding")
      .closest("tr");
    expect(noLinkRow).toHaveTextContent("-");
  });

  it('renders "-" instead of a clickable link for a javascript: link', () => {
    render(
      <TrainingSection
        list={[
          {
            id: 1,
            category: "corporate_culture_course",
            status: "done",
            link: "javascript:alert(1)",
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(
      screen.getByText("Corporate Culture Course").closest("tr"),
    ).toHaveTextContent("-");
  });
});
