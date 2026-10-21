import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MentorshipManagement from "@/pages/MentorshipManagement";
import { useMentorshipManagement } from "@/pages/MentorshipManagement/hooks/useMentorshipManagement";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { useMyMentorshipApprovals } from "@/pages/MentorshipManagement/hooks/useMyMentorshipApprovals";

vi.mock("@/pages/MentorshipManagement/hooks/useMentorshipManagement", () => ({
  useMentorshipManagement: vi.fn(),
}));

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

vi.mock("@/pages/MentorshipManagement/hooks/useMyMentorshipApprovals", () => ({
  useMyMentorshipApprovals: vi.fn(),
}));

vi.mock("@/pages/MentorshipManagement/components/PendingApprovalsCard", () => ({
  default: vi.fn(({ requests }) => (
    <div data-testid="mock-pending-approvals">{requests.length}</div>
  )),
}));

vi.mock("@/pages/MentorshipManagement/components/RoundsManagementCard", () => ({
  default: vi.fn(
    ({
      rounds,
      totals,
      isLoading,
      openCreate,
      openEdit,
      canWriteRounds,
      canReadFeedback,
    }) => (
      <div data-testid="mock-rounds-management-card">
        <span data-testid="rounds-count">{rounds.length}</span>
        <span data-testid="is-loading">{String(isLoading)}</span>
        <span data-testid="total-completed-rounds">
          {totals?.totalCompletedRounds}
        </span>
        <span data-testid="can-write">{String(canWriteRounds)}</span>
        <span data-testid="can-read-feedback">{String(canReadFeedback)}</span>
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
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.MATCHING_RUN]: true });
    useMyMentorshipApprovals.mockReturnValue({ requests: [] });
    useAuth.mockReturnValue({
      permissions: [
        PERMISSIONS.MENTORSHIP_ADMIN_READ,
        PERMISSIONS.MENTORSHIP_ADMIN_WRITE,
      ],
    });
  });

  it("leads with the requests waiting on an approver", () => {
    useAuth.mockReturnValue({
      permissions: [
        PERMISSIONS.MENTORSHIP_ADMIN_READ,
        PERMISSIONS.MENTORSHIP_APPROVE,
      ],
    });
    useMyMentorshipApprovals.mockReturnValue({
      requests: [{ requestId: 31 }, { requestId: 32 }],
    });

    render(<MentorshipManagement />);

    expect(useMyMentorshipApprovals).toHaveBeenCalledWith(true);
    expect(screen.getByTestId("mock-pending-approvals").textContent).toBe("2");
  });

  it("asks for no approvals without mentorship.approve or the flag", () => {
    render(<MentorshipManagement />);
    expect(useMyMentorshipApprovals).toHaveBeenLastCalledWith(false);

    useAuth.mockReturnValue({ permissions: [PERMISSIONS.MENTORSHIP_APPROVE] });
    useFeatureFlags.mockReturnValue({});
    render(<MentorshipManagement />);
    expect(useMyMentorshipApprovals).toHaveBeenLastCalledWith(false);
    expect(
      screen.queryByTestId("mock-pending-approvals"),
    ).not.toBeInTheDocument();
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

  it("renders the card and forwards the write flag with admin-write permission", () => {
    render(<MentorshipManagement />);
    expect(
      screen.getByTestId("mock-rounds-management-card"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("can-write").textContent).toBe("true");
    // The read flag also drives whether the hook fetches rounds.
    expect(useMentorshipManagement).toHaveBeenCalledWith(true);
  });

  it("does not render the card when the user lacks admin-read permission", () => {
    useAuth.mockReturnValue({ permissions: [] });
    render(<MentorshipManagement />);
    expect(
      screen.queryByTestId("mock-rounds-management-card"),
    ).not.toBeInTheDocument();
    expect(useMentorshipManagement).toHaveBeenCalledWith(false);
  });

  it("does not render ParticipantSearchCard when the user lacks admin-read permission", () => {
    useAuth.mockReturnValue({ permissions: [] });
    render(<MentorshipManagement />);
    expect(
      screen.queryByTestId("mock-participant-search-card"),
    ).not.toBeInTheDocument();
  });

  it("renders the card without write controls for an admin-read-only user", () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.MENTORSHIP_ADMIN_READ],
    });
    render(<MentorshipManagement />);
    expect(
      screen.getByTestId("mock-rounds-management-card"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("can-write").textContent).toBe("false");
    expect(screen.getByTestId("can-read-feedback").textContent).toBe("true");
  });

  it("renders ParticipantSearchCard when the user has admin-read permission", () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.MENTORSHIP_ADMIN_READ],
    });
    render(<MentorshipManagement />);
    expect(
      screen.getByTestId("mock-participant-search-card"),
    ).toBeInTheDocument();
  });

  it("renders the card with write controls for a write-only user, without ParticipantSearchCard", () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.MENTORSHIP_ADMIN_WRITE],
    });
    render(<MentorshipManagement />);
    expect(
      screen.getByTestId("mock-rounds-management-card"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("can-write").textContent).toBe("true");
    // Feedback is read-only data: write alone does not show it.
    expect(screen.getByTestId("can-read-feedback").textContent).toBe("false");
    expect(
      screen.queryByTestId("mock-participant-search-card"),
    ).not.toBeInTheDocument();
    // canRead is false for a write-only user, forwarded to the hook.
    expect(useMentorshipManagement).toHaveBeenCalledWith(false);
  });
});
