import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom";

import TrainingSection from "@/pages/Profile/components/TrainingSection";

const renderInRouter = (ui) => render(ui, { wrapper: MemoryRouter });

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

  it("notes which timezone the dates are shown in", () => {
    render(
      <TrainingSection
        list={TRAINING_FIXTURES.single}
        timezone="Asia/Shanghai"
      />,
    );

    expect(
      screen.getByText("Dates shown in Asia/Shanghai."),
    ).toBeInTheDocument();
  });

  it("does not show a timezone note when there are no training records", () => {
    render(<TrainingSection list={[]} />);

    expect(screen.queryByText(/Dates shown in/)).not.toBeInTheDocument();
  });

  it("renders empty state when list is empty or null", () => {
    const { rerender } = render(<TrainingSection list={[]} />);
    expect(screen.getByText("No training records found.")).toBeInTheDocument();

    rerender(<TrainingSection list={null} />);
    expect(screen.getByText("No training records found.")).toBeInTheDocument();
  });

  it("renders the friendly category label and the actual day for each timestamp", () => {
    render(
      <TrainingSection
        list={TRAINING_FIXTURES.single}
        timezone="America/Los_Angeles"
      />,
    );

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(
      screen.getByText("Mentorship Mentor Onboarding"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("mentorship_mentor_onboarding"),
    ).not.toBeInTheDocument();

    // Full calendar day, not just month/year. 2023-01-15T00:00:00Z is
    // midnight UTC, which in Los Angeles (UTC-8 in January) is still
    // the previous day.
    expect(screen.getByText("Jan 14, 2023")).toBeInTheDocument();
    expect(screen.getByText("Feb 14, 2023")).toBeInTheDocument();
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

    const notStartedTag = screen.getByText("Not Started");
    expect(notStartedTag).toBeInTheDocument();
    expect(notStartedTag).toHaveClass("bg-primary", "text-primary-foreground");
  });

  it("gives the in-progress status its own badge, distinct from the other two", () => {
    render(
      <TrainingSection
        list={[
          {
            id: 1,
            category: "mentorship_mentor_onboarding",
            status: "in_progress",
            link: "",
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    const badge = screen.getByText("In Progress");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("bg-secondary", "text-secondary-foreground");
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
        timezone="America/Los_Angeles"
      />,
    );

    // Sentinel completed_timestamp → "-"; real deadline → actual day in
    // America/Los_Angeles (UTC-7 in May).
    expect(screen.getByText("-")).toBeInTheDocument();
    expect(screen.getByText("May 17, 2026")).toBeInTheDocument();
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

  it("names the row by its course, not by the category", () => {
    renderInRouter(
      <TrainingSection
        list={[
          {
            id: 1,
            courseId: 7,
            name: "Mentor Onboarding",
            category: null,
            status: "to_do",
            link: null,
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    expect(screen.getByText("Mentor Onboarding")).toBeInTheDocument();
  });

  it("opens a hosted course in the app when the row has no external link", () => {
    renderInRouter(
      <TrainingSection
        list={[
          {
            id: 42,
            courseId: 7,
            isHosted: true,
            name: "Mentor Onboarding",
            category: null,
            status: "to_do",
            link: null,
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    expect(screen.getByRole("link", { name: /^start$/i })).toHaveAttribute(
      "href",
      "/training/42",
    );
  });

  it("keeps sending a seed row to its external link", () => {
    renderInRouter(
      <TrainingSection
        list={[
          {
            id: 42,
            courseId: 7,
            name: "Corporate Culture",
            category: "corporate_culture_course",
            status: "done",
            link: "http://test.com",
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    expect(screen.getByRole("link", { name: /view link/i })).toHaveAttribute(
      "href",
      "http://test.com",
    );
    expect(
      screen.queryByRole("link", { name: /^review$/i }),
    ).not.toBeInTheDocument();
  });

  it("names the action after where the learner actually is", () => {
    renderInRouter(
      <TrainingSection
        list={[
          {
            id: 1,
            courseId: 7,
            isHosted: true,
            name: "A",
            status: "to_do",
            link: null,
            ...BASE_TIMESTAMPS,
          },
          {
            id: 2,
            courseId: 7,
            isHosted: true,
            name: "B",
            status: "in_progress",
            link: null,
            ...BASE_TIMESTAMPS,
          },
          {
            id: 3,
            courseId: 7,
            isHosted: true,
            name: "C",
            status: "done",
            link: null,
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    expect(screen.getByRole("link", { name: /^start$/i })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /^continue$/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^review$/i })).toBeInTheDocument();
  });

  it("calls reopening a finished course Review, never Retake", () => {
    // Opening a completed course must not move it out of Done. Naming it
    // Retake invites the learner to expect that it would.
    renderInRouter(
      <TrainingSection
        list={[
          {
            id: 3,
            courseId: 7,
            isHosted: true,
            name: "C",
            status: "done",
            link: null,
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    expect(screen.queryByText(/retake/i)).not.toBeInTheDocument();
  });

  it("offers nothing to click on a course with no package and no link", () => {
    // A seed course nobody has uploaded to, in an environment whose link
    // variable is unset. Start would open the course and raise.
    renderInRouter(
      <TrainingSection
        list={[
          {
            id: 42,
            courseId: 7,
            isHosted: false,
            name: "Residency Onboarding",
            category: "residency_program_onboarding",
            status: "to_do",
            link: null,
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByText(/^start$/i)).not.toBeInTheDocument();
  });

  it("still names a row the catalogue holds no course for", () => {
    renderInRouter(
      <TrainingSection
        list={[
          {
            id: 1,
            courseId: null,
            name: null,
            category: "corporate_culture_course",
            status: "done",
            link: null,
            ...BASE_TIMESTAMPS,
          },
        ]}
      />,
    );

    expect(screen.getByText("Corporate Culture Course")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
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
