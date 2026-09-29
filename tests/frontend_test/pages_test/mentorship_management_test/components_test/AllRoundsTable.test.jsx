import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import AllRoundsTable from "@/pages/MentorshipManagement/components/AllRoundsTable";

const makeTestRound = (overrides = {}) => ({
  id: 1,
  name: "Mentorship 2026 Spring",
  activePairs: 26,
  matchedParticipants: 52,
  totalCompletedMeetings: 93,
  menteeAverageScore: 4.8,
  mentorAverageScore: null,
  requiredMeetings: 5,
  ...overrides,
});

const renderTable = (rounds, totals, onEdit = vi.fn()) =>
  render(<AllRoundsTable rounds={rounds} totals={totals} onEdit={onEdit} />);

describe("AllRoundsTable", () => {
  it("renders all column headers", () => {
    renderTable([]);

    [
      "Round Name",
      "Participants",
      "Required Meetings",
      "Mentor Rating",
      "Mentee Rating",
      "Average Meetings Per Pair",
    ].forEach((col) => expect(screen.getByText(col)).toBeInTheDocument());
  });

  it("renders round data correctly", () => {
    renderTable([makeTestRound()]);

    expect(screen.getByText("Mentorship 2026 Spring")).toBeInTheDocument();
    expect(screen.getByText("52")).toBeInTheDocument(); // matchedParticipants
    expect(screen.getByText("5 times")).toBeInTheDocument(); // requiredMeetings
    expect(screen.getByText("4.80")).toBeInTheDocument(); // menteeAverageScore
    expect(screen.getByText("3.6")).toBeInTheDocument(); // 93 / 26
  });

  it("shows '—' for all null stats", () => {
    renderTable([
      makeTestRound({
        activePairs: null,
        matchedParticipants: null,
        totalCompletedMeetings: null,
        menteeAverageScore: null,
        mentorAverageScore: null,
      }),
    ]);

    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("shows '—' for avgMeetings when activePairs is 0", () => {
    renderTable([
      makeTestRound({
        activePairs: 0,
        totalCompletedMeetings: 10,
        mentorAverageScore: 4.5,
      }),
    ]);

    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders footer totals", () => {
    renderTable([], {
      totalCompletedRounds: 5,
      totalParticipants: 255,
      totalMeetings: 373,
    });

    expect(screen.getByText(/Total Completed Rounds:/).textContent).toContain(
      "5",
    );
    expect(screen.getByText(/Total Participants:/).textContent).toContain(
      "255",
    );
    expect(screen.getByText(/Total Meetings:/).textContent).toContain("373");
  });

  it("calls onEdit with the correct round", async () => {
    const onEdit = vi.fn();
    const round1 = makeTestRound();
    const round2 = makeTestRound({
      id: 2,
      name: "Mentorship 2025 Fall",
      activePairs: 25,
      matchedParticipants: 50,
      totalCompletedMeetings: 99,
    });
    renderTable([round1, round2], undefined, onEdit);

    const editButtons = screen.getAllByRole("button", { name: /edit round/i });
    await userEvent.click(editButtons[1]);

    expect(onEdit).toHaveBeenCalledWith(round2);
  });

  it("shows the Action column and edit buttons when canEdit is true", () => {
    render(
      <AllRoundsTable rounds={[makeTestRound()]} onEdit={vi.fn()} canEdit />,
    );

    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /edit round/i }),
    ).toBeInTheDocument();
  });

  it("shows a view button instead of an edit button when canEdit is false", () => {
    render(
      <AllRoundsTable
        rounds={[makeTestRound()]}
        onEdit={vi.fn()}
        canEdit={false}
      />,
    );

    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /edit round/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /view round/i }),
    ).toBeInTheDocument();
  });

  describe("Feedback column", () => {
    const renderWithFeedback = (rounds, canReadFeedback = true) =>
      render(
        <MemoryRouter>
          <AllRoundsTable
            rounds={rounds}
            totals={{}}
            onEdit={vi.fn()}
            canReadFeedback={canReadFeedback}
          />
        </MemoryRouter>,
      );

    it("links sent of owed to the round's feedback page", () => {
      renderWithFeedback([
        makeTestRound({ id: 7, feedbackOwed: 8, feedbackSent: 3 }),
      ]);

      expect(screen.getByText("Feedback")).toBeInTheDocument();
      const link = screen.getByRole("link", {
        name: "Feedback for Mentorship 2026 Spring",
      });
      expect(link).toHaveTextContent("3 of 8 sent");
      expect(link).toHaveAttribute(
        "href",
        "/mentorship-management/rounds/7/feedback",
      );
    });

    it("shows a dash, not a link, when nobody owes feedback", () => {
      renderWithFeedback([makeTestRound({ feedbackOwed: 0, feedbackSent: 0 })]);

      expect(screen.queryByRole("link")).not.toBeInTheDocument();
    });

    it("leaves the column out without read permission", () => {
      renderWithFeedback(
        [makeTestRound({ feedbackOwed: 8, feedbackSent: 3 })],
        false,
      );

      expect(screen.queryByText("Feedback")).not.toBeInTheDocument();
      expect(screen.queryByText("3 of 8 sent")).not.toBeInTheDocument();
    });
  });
});
