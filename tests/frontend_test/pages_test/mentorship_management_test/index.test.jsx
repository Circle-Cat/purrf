import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MentorshipManagement from "@/pages/MentorshipManagement";
import { useMentorshipManagement } from "@/pages/MentorshipManagement/hooks/useMentorshipManagement";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";

vi.mock("@/pages/MentorshipManagement/hooks/useMentorshipManagement", () => ({
  useMentorshipManagement: vi.fn(),
}));

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/pages/MentorshipManagement/components/RoundsManagementCard", () => ({
  default: vi.fn(
    ({ rounds, totals, isLoading, openCreate, openEdit, canWriteRounds }) => (
      <div data-testid="mock-rounds-management-card">
        <span data-testid="rounds-count">{rounds.length}</span>
        <span data-testid="is-loading">{String(isLoading)}</span>
        <span data-testid="total-completed-rounds">
          {totals?.totalCompletedRounds}
        </span>
        <span data-testid="can-write">{String(canWriteRounds)}</span>
        <button onClick={openCreate}>Create</button>
        <button onClick={() => openEdit(rounds[0])}>Edit</button>
      </div>
    ),
  ),
}));

vi.mock(
  "@/pages/MentorshipManagement/components/ParticipantSearchCard",
  () => ({
    default: vi.fn(() => <div data-testid="mock-participant-search-card" />),
  }),
);

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
  saveRound: vi.fn(),
};

describe("MentorshipManagement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useMentorshipManagement.mockReturnValue(defaultHookData);
    useAuth.mockReturnValue({
      permissions: [
        PERMISSIONS.MENTORSHIP_ROUND_READ,
        PERMISSIONS.MENTORSHIP_ROUND_WRITE,
      ],
    });
  });

  it("passes rounds and totals to RoundsManagementCard", () => {
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

  it("renders the card and forwards the write flag with round-read permission", () => {
    render(<MentorshipManagement />);
    expect(
      screen.getByTestId("mock-rounds-management-card"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("can-write").textContent).toBe("true");
    // The read flag also drives whether the hook fetches rounds.
    expect(useMentorshipManagement).toHaveBeenCalledWith(true);
  });

  it("does not render the card when the user lacks round-read permission", () => {
    useAuth.mockReturnValue({ permissions: [] });
    render(<MentorshipManagement />);
    expect(
      screen.queryByTestId("mock-rounds-management-card"),
    ).not.toBeInTheDocument();
    expect(useMentorshipManagement).toHaveBeenCalledWith(false);
  });

  it("renders the card without write controls for a round-read-only user", () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.MENTORSHIP_ROUND_READ],
    });
    render(<MentorshipManagement />);
    expect(
      screen.getByTestId("mock-rounds-management-card"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("can-write").textContent).toBe("false");
  });

  it("renders ParticipantSearchCard when the user has participant-read", () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.MENTORSHIP_PARTICIPANT_READ],
    });
    render(<MentorshipManagement />);
    expect(
      screen.getByTestId("mock-participant-search-card"),
    ).toBeInTheDocument();
  });

  it("does not render ParticipantSearchCard when the user lacks participant-read", () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.MENTORSHIP_ROUND_READ],
    });
    render(<MentorshipManagement />);
    expect(
      screen.queryByTestId("mock-participant-search-card"),
    ).not.toBeInTheDocument();
  });
});
