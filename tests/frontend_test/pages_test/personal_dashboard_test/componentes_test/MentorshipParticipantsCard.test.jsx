import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MentorshipParticipantsCard from "@/pages/PersonalDashboard/components/MentorshipParticipantsCard";
import { MentorshipRoundStatus } from "@/constants/MentorshipRoundStatus";

const { mockUseFlags } = vi.hoisted(() => ({
  mockUseFlags: vi.fn(),
}));

vi.mock("@/hooks/useFeatureFlags", () => ({
  useFeatureFlags: mockUseFlags,
}));

vi.mock("@/pages/PersonalDashboard/components/MeetingSubmissionModal", () => ({
  default: ({ open, onSuccess, userTimezone }) =>
    open ? (
      <div data-testid="meeting-modal" data-user-timezone={userTimezone}>
        <button onClick={onSuccess}>mock-success</button>
      </div>
    ) : null,
}));

vi.mock("@/pages/PersonalDashboard/components/MeetingOverviewCard", () => ({
  default: ({ overview }) => (
    <div data-testid={`overview-${overview.partnerId}`} />
  ),
}));

const baseProps = {
  roundSelectionData: {
    sortedRounds: [{ id: "1", name: "2026 Spring", status: "active" }],
  },
  selectedRoundId: "1",
  onRoundChange: vi.fn(),
  isParticipantCardLoading: false,
  participantDetails: {
    roundInfo: {
      name: "2026 Spring",
      status: "active",
      timeline: {
        matchNotificationAt: "2026-02-10T07:59:59Z",
        meetingsCompletionDeadlineAt: "2026-04-30T06:59:59Z",
      },
    },
    partnerMeetingOverview: [
      {
        partnerId: 1,
        preferredName: "Alice",
        requiredMeetings: 3,
        completedCount: 1,
        completedRate: 33,
        meetingTimeList: [],
        participantRole: "mentee",
      },
    ],
    participantRole: "mentee",
  },
  refreshMeetings: vi.fn(),
  userTimezone: "Asia/Shanghai",
};

describe("MentorshipParticipantsCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseFlags.mockReturnValue({ "manual-submit-meeting": true });
  });

  it("should show a loading message while data is loading", () => {
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        isParticipantCardLoading={true}
      />,
    );
    expect(screen.getByText(/Loading participation data/)).toBeInTheDocument();
  });

  it("should show 'not participated' message when the user has no participation", () => {
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          roundInfo: null,
          partnerMeetingOverview: [],
          participantRole: null,
        }}
      />,
    );
    expect(screen.getByText(/You have not participated/)).toBeInTheDocument();
  });

  it("should show 'registered but not matched' message when user is registered with no partners", () => {
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          roundInfo: null,
          partnerMeetingOverview: [],
          participantRole: null,
          isRegistered: true,
        }}
      />,
    );
    expect(
      screen.getByText(
        /You are registered for this round but have not been matched yet/,
      ),
    ).toBeInTheDocument();
  });

  it("should show the submit meeting button for mentees", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    expect(
      screen.getByRole("button", { name: /Submit Meeting Info/ }),
    ).toBeInTheDocument();
  });

  it("should NOT show the submit meeting button for mentors", () => {
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          ...baseProps.participantDetails,
          participantRole: "mentor",
        }}
      />,
    );
    expect(
      screen.queryByRole("button", { name: /Submit Meeting Info/ }),
    ).not.toBeInTheDocument();
  });

  it("should display 'Mentor:' when the user is a mentee", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    expect(screen.getByText(/Mentor:/)).toBeInTheDocument();
  });

  it("should capitalize and display the user role", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    const roleLabel = screen.getByText("Role:", { selector: "span" });
    expect(roleLabel.closest("p")).toHaveTextContent("Role: Mentee");
  });

  it("should pass userTimezone from the first partner to the modal", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    fireEvent.click(
      screen.getByRole("button", { name: /Submit Meeting Info/ }),
    );
    expect(screen.getByTestId("meeting-modal")).toHaveAttribute(
      "data-user-timezone",
      "Asia/Shanghai",
    );
  });

  it("should render a MeetingOverviewCard for each partner", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    expect(screen.getByTestId("overview-1")).toBeInTheDocument();
  });

  it("should open the meeting modal when the submit button is clicked", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    fireEvent.click(
      screen.getByRole("button", { name: /Submit Meeting Info/ }),
    );
    expect(screen.getByTestId("meeting-modal")).toBeInTheDocument();
  });

  it("should call refreshMeetings after successful meeting submission", () => {
    const refreshMeetings = vi.fn();

    render(
      <MentorshipParticipantsCard
        {...baseProps}
        refreshMeetings={refreshMeetings}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: /Submit Meeting Info/ }),
    );
    expect(screen.getByTestId("meeting-modal")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "mock-success" }));
    expect(refreshMeetings).toHaveBeenCalled();
  });

  it("should NOT show submit button when flag is off", () => {
    mockUseFlags.mockReturnValue({ "manual-submit-meeting": false });
    render(<MentorshipParticipantsCard {...baseProps} />);

    expect(
      screen.queryByRole("button", { name: /Submit Meeting Info/ }),
    ).not.toBeInTheDocument();
  });

  it("should show submit button when flag is on", () => {
    mockUseFlags.mockReturnValue({ "manual-submit-meeting": true });
    render(<MentorshipParticipantsCard {...baseProps} />);

    expect(
      screen.getByRole("button", { name: /Submit Meeting Info/ }),
    ).toBeInTheDocument();
  });

  it("should not render meeting modal when user cannot submit", () => {
    mockUseFlags.mockReturnValue({ "manual-submit-meeting": false });
    render(<MentorshipParticipantsCard {...baseProps} />);

    expect(screen.queryByTestId("meeting-modal")).not.toBeInTheDocument();
  });

  it("should display duration as date only", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    const durationEl = screen
      .getByText("Duration:", { selector: "span" })
      .closest("p");
    expect(durationEl).toHaveTextContent(
      /\d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}/,
    );
  });

  it("should keep submit enabled when deadline is in the future", () => {
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          ...baseProps.participantDetails,
          roundInfo: {
            ...baseProps.participantDetails.roundInfo,
            status: MentorshipRoundStatus.ACTIVE,
            timeline: { meetingsCompletionDeadlineAt: "2099-12-31T00:00:00Z" },
          },
        }}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Submit Meeting Info/ }),
    ).not.toBeDisabled();
  });

  it("should disable submit when deadline is well in the past", () => {
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          ...baseProps.participantDetails,
          roundInfo: {
            ...baseProps.participantDetails.roundInfo,
            status: MentorshipRoundStatus.ACTIVE,
            timeline: { meetingsCompletionDeadlineAt: "2020-01-01T00:00:00Z" },
          },
        }}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Submit Meeting Info/ }),
    ).toBeDisabled();
  });

  it("should disable submit when round is completed without deadline", () => {
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          ...baseProps.participantDetails,
          roundInfo: {
            ...baseProps.participantDetails.roundInfo,
            status: MentorshipRoundStatus.COMPLETED,
            timeline: { meetingsCompletionDeadlineAt: undefined },
          },
        }}
      />,
    );

    expect(
      screen.getByRole("button", { name: /Submit Meeting Info/ }),
    ).toBeDisabled();
  });
});
