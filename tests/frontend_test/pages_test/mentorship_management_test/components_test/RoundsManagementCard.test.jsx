import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import RoundsManagementCard from "@/pages/MentorshipManagement/components/RoundsManagementCard";

vi.mock("@/pages/MentorshipManagement/components/AllRoundsTable", () => ({
  default: vi.fn(({ rounds, onEdit }) => (
    <div data-testid="mock-all-rounds-table">
      <span data-testid="rounds-count">{rounds.length}</span>
      <button onClick={() => onEdit(rounds[0])}>Edit First Round</button>
    </div>
  )),
}));

const defaultRound = {
  id: 1,
  name: "Mentorship 2026 Spring",
  activePairs: 26,
  matchedParticipants: 52,
  totalCompletedMeetings: 93,
  requiredMeetings: 5,
};

const defaultProps = {
  rounds: [defaultRound],
  totals: { totalCompletedRounds: 1, totalParticipants: 52, totalMeetings: 93 },
  isLoading: false,
  openCreate: vi.fn(),
  openEdit: vi.fn(),
};

const renderCard = (props = {}) =>
  render(<RoundsManagementCard {...defaultProps} {...props} />);

describe("RoundsManagementCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the card title", () => {
    renderCard();
    expect(screen.getByText("Mentorship Round Management")).toBeInTheDocument();
  });

  it("renders the Create New Round button", () => {
    renderCard();
    expect(
      screen.getByRole("button", { name: /create new round/i }),
    ).toBeInTheDocument();
  });

  it("shows loading state when isLoading is true", () => {
    renderCard({ isLoading: true });
    expect(screen.getByText(/loading rounds/i)).toBeInTheDocument();
    expect(
      screen.queryByTestId("mock-all-rounds-table"),
    ).not.toBeInTheDocument();
  });

  it("renders AllRoundsTable when not loading and rounds exist", () => {
    renderCard();
    expect(screen.getByTestId("mock-all-rounds-table")).toBeInTheDocument();
  });

  it("shows empty state when rounds is empty", () => {
    renderCard({ rounds: [] });
    expect(
      screen.queryByTestId("mock-all-rounds-table"),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/no rounds found/i)).toBeInTheDocument();
  });

  it("calls openCreate when Create New Round is clicked", async () => {
    const openCreate = vi.fn();
    renderCard({ openCreate });
    await userEvent.click(
      screen.getByRole("button", { name: /create new round/i }),
    );
    expect(openCreate).toHaveBeenCalledTimes(1);
  });

  it("calls openEdit with the round when AllRoundsTable triggers onEdit", async () => {
    const openEdit = vi.fn();
    renderCard({ openEdit });
    await userEvent.click(
      screen.getByRole("button", { name: /edit first round/i }),
    );
    expect(openEdit).toHaveBeenCalledWith(defaultRound);
  });
});
