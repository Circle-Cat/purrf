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
    ({
      rounds,
      totals,
      isLoading,
      openCreate,
      openEdit,
      canReadRounds,
      canWriteRounds,
    }) => (
      <div data-testid="mock-rounds-management-card">
        <span data-testid="rounds-count">{rounds.length}</span>
        <span data-testid="is-loading">{String(isLoading)}</span>
        <span data-testid="total-completed-rounds">
          {totals?.totalCompletedRounds}
        </span>
        <span data-testid="can-read">{String(canReadRounds)}</span>
        <span data-testid="can-write">{String(canWriteRounds)}</span>
        <button onClick={openCreate}>Create</button>
        <button onClick={() => openEdit(rounds[0])}>Edit</button>
      </div>
    ),
  ),
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

  it("derives read/write flags from permissions and forwards them", () => {
    render(<MentorshipManagement />);
    expect(screen.getByTestId("can-read").textContent).toBe("true");
    expect(screen.getByTestId("can-write").textContent).toBe("true");
    // The read flag also drives whether the hook fetches rounds.
    expect(useMentorshipManagement).toHaveBeenCalledWith(true);
  });

  it("marks read/write false when the user lacks the round permissions", () => {
    useAuth.mockReturnValue({ permissions: [] });
    render(<MentorshipManagement />);
    expect(screen.getByTestId("can-read").textContent).toBe("false");
    expect(screen.getByTestId("can-write").textContent).toBe("false");
    expect(useMentorshipManagement).toHaveBeenCalledWith(false);
  });

  it("allows read without write for a round-read-only user", () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.MENTORSHIP_ROUND_READ],
    });
    render(<MentorshipManagement />);
    expect(screen.getByTestId("can-read").textContent).toBe("true");
    expect(screen.getByTestId("can-write").textContent).toBe("false");
  });
});
