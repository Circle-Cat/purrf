import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MentorshipManagement from "@/pages/MentorshipManagement";
import { useMentorshipManagement } from "@/pages/MentorshipManagement/hooks/useMentorshipManagement";

vi.mock("@/pages/MentorshipManagement/hooks/useMentorshipManagement", () => ({
  useMentorshipManagement: vi.fn(),
}));

vi.mock("@/pages/MentorshipManagement/components/RoundsManagementCard", () => ({
  default: vi.fn(({ rounds, totals, isLoading, openCreate, openEdit }) => (
    <div data-testid="mock-rounds-management-card">
      <span data-testid="rounds-count">{rounds.length}</span>
      <span data-testid="is-loading">{String(isLoading)}</span>
      <span data-testid="total-completed-rounds">
        {totals?.totalCompletedRounds}
      </span>
      <button onClick={openCreate}>Create</button>
      <button onClick={() => openEdit(rounds[0])}>Edit</button>
    </div>
  )),
}));

const defaultHookData = {
  sortedRounds: [
    {
      id: 1,
      name: "Mentorship 2026 Spring",
      activePairs: 26,
      matchedParticipants: 52,
      totalCompletedMeetings: 93,
      requiredMeetings: 5,
    },
  ],
  totals: { totalCompletedRounds: 1, totalParticipants: 52, totalMeetings: 93 },
  isLoading: false,
  roundModalState: { open: false, round: null },
  openCreate: vi.fn(),
  openEdit: vi.fn(),
  closeModal: vi.fn(),
};

describe("MentorshipManagement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useMentorshipManagement.mockReturnValue(defaultHookData);
  });

  it("renders RoundsManagementCard", () => {
    render(<MentorshipManagement />);
    expect(
      screen.getByTestId("mock-rounds-management-card"),
    ).toBeInTheDocument();
  });

  it("passes sortedRounds and totals to RoundsManagementCard", () => {
    render(<MentorshipManagement />);
    expect(screen.getByTestId("rounds-count").textContent).toBe("1");
    expect(screen.getByTestId("total-completed-rounds").textContent).toBe("1");
  });

  it("passes isLoading to RoundsManagementCard", () => {
    useMentorshipManagement.mockReturnValue({
      ...defaultHookData,
      isLoading: true,
    });
    render(<MentorshipManagement />);
    expect(screen.getByTestId("is-loading").textContent).toBe("true");
  });
});
