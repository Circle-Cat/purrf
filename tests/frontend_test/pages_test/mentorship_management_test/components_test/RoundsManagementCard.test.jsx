import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import RoundsManagementCard from "@/pages/MentorshipManagement/components/RoundsManagementCard";
import AllRoundsTable from "@/pages/MentorshipManagement/components/AllRoundsTable";

vi.mock("@/pages/MentorshipManagement/components/AllRoundsTable", () => ({
  default: vi.fn(({ rounds, onEdit }) => (
    <div data-testid="mock-all-rounds-table">
      <span data-testid="rounds-count">{rounds.length}</span>
      <button onClick={() => onEdit(rounds[0])}>Edit First Round</button>
    </div>
  )),
}));

vi.mock("@/pages/MentorshipManagement/components/RoundModal", () => ({
  default: vi.fn(({ open, onClose }) =>
    open ? (
      <div data-testid="mock-round-modal">
        <button onClick={onClose}>Close Modal</button>
      </div>
    ) : null,
  ),
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
  roundModalState: { open: false, round: null },
  openCreate: vi.fn(),
  openEdit: vi.fn(),
  closeModal: vi.fn(),
  saveRound: vi.fn(),
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

  it("renders RoundModal only when roundModalState.open is true", () => {
    const { rerender } = renderCard();
    expect(screen.queryByTestId("mock-round-modal")).not.toBeInTheDocument();
    rerender(
      <RoundsManagementCard
        {...defaultProps}
        roundModalState={{ open: true, round: null }}
      />,
    );
    expect(screen.getByTestId("mock-round-modal")).toBeInTheDocument();
  });

  it("calls closeModal when RoundModal closes", async () => {
    const closeModal = vi.fn();
    renderCard({ roundModalState: { open: true, round: null }, closeModal });
    await userEvent.click(screen.getByRole("button", { name: /close modal/i }));
    expect(closeModal).toHaveBeenCalledTimes(1);
  });

  it("hides the Create New Round button without write permission", () => {
    renderCard({ canWriteRounds: false });
    expect(
      screen.queryByRole("button", { name: /create new round/i }),
    ).not.toBeInTheDocument();
  });

  it("shows a no-permission message and hides the table without read permission", () => {
    renderCard({ canReadRounds: false });
    expect(
      screen.getByText(/permission to view mentorship rounds/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("mock-all-rounds-table"),
    ).not.toBeInTheDocument();
  });

  it("forwards canWriteRounds to AllRoundsTable as canEdit", () => {
    renderCard({ canWriteRounds: false });
    const tableMock = AllRoundsTable;
    expect(tableMock).toHaveBeenCalled();
    expect(tableMock.mock.calls[0][0].canEdit).toBe(false);
  });
});
