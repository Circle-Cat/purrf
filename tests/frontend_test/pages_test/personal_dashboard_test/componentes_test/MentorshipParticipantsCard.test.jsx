import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import MentorshipParticipantsCard from "@/pages/PersonalDashboard/components/MentorshipParticipantsCard";
import { MentorshipRoundStatus } from "@/constants/MentorshipRoundStatus";

const { mockUseFlags } = vi.hoisted(() => ({
  mockUseFlags: vi.fn(),
}));

vi.mock("@/hooks/useFeatureFlags", () => ({
  useFeatureFlags: mockUseFlags,
}));

vi.mock("@/pages/PersonalDashboard/components/MeetingSubmissionModal", () => ({
  default: ({ open, onSuccess, userTimezone, partnerId }) =>
    open ? (
      <div
        data-testid="meeting-modal"
        data-user-timezone={userTimezone}
        data-partner-id={String(partnerId)}
      >
        <button onClick={onSuccess}>mock-success</button>
      </div>
    ) : null,
}));

vi.mock("@/pages/PersonalDashboard/components/MeetingOverviewCard", () => ({
  default: ({ overview }) => (
    <div data-testid={`overview-${overview.partnerId}`} />
  ),
}));

vi.mock(
  "@/pages/PersonalDashboard/components/MentorshipFeedbackDialog",
  () => ({
    default: ({ roundId, roundName, isEditable, feedbackDeadlineText }) => (
      <div
        data-testid="feedback-dialog"
        data-round-id={roundId}
        data-round-name={roundName}
        data-editable={String(isEditable)}
        data-deadline={feedbackDeadlineText ?? ""}
      />
    ),
  }),
);

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
    // Pin "now" inside the round window so the submit modal stays
    // available; otherwise the real system clock can drift past
    // meetingsCompletionDeadlineAt and hide the meeting modal.
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-01T00:00:00Z"));
    mockUseFlags.mockReturnValue({ "manual-submit-meeting": true });
  });

  afterEach(() => {
    vi.useRealTimers();
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

  it("should pass the partner to the modal", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    fireEvent.click(
      screen.getByRole("button", { name: /Submit Meeting Info/ }),
    );
    expect(screen.getByTestId("meeting-modal")).toHaveAttribute(
      "data-partner-id",
      "1",
    );
  });

  it("should disable submitting while more than one partner is shown", () => {
    // The modal is one per round, so it can only name a partner while there
    // is exactly one to name. Two would leave the target pair ambiguous, and
    // submitting against the wrong one is worse than not submitting.
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          ...baseProps.participantDetails,
          partnerMeetingOverview: [
            ...baseProps.participantDetails.partnerMeetingOverview,
            {
              partnerId: 2,
              preferredName: "Bob",
              requiredMeetings: 3,
              completedCount: 0,
              completedRate: 0,
              meetingTimeList: [],
              participantRole: "mentee",
            },
          ],
        }}
      />,
    );

    expect(
      screen.getByRole("button", { name: /Submit Meeting Info/ }),
    ).toBeDisabled();
    expect(screen.queryByTestId("meeting-modal")).not.toBeInTheDocument();
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

  it("should display duration as date only, labelled with the viewer's timezone", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    const durationEl = screen
      .getByText("Duration:", { selector: "span" })
      .closest("p");
    expect(durationEl).toHaveTextContent(
      /\d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2} Asia\/Shanghai/,
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

  // "now" is pinned to 2026-03-01T00:00:00Z by the beforeEach above.
  describe("feedback dialog", () => {
    const renderWithTimeline = (timeline) =>
      render(
        <MentorshipParticipantsCard
          {...baseProps}
          participantDetails={{
            ...baseProps.participantDetails,
            roundInfo: {
              ...baseProps.participantDetails.roundInfo,
              timeline,
            },
          }}
        />,
      );

    it("should not render the dialog before the feedback window opens", () => {
      renderWithTimeline({
        meetingLogReminderAt: "2026-04-02T06:59:59Z",
        meetingsCompletionDeadlineAt: "2026-04-30T06:59:59Z",
        feedbackDeadlineAt: "2026-05-09T15:59:59Z",
      });
      expect(screen.queryByTestId("feedback-dialog")).not.toBeInTheDocument();
    });

    it("should render an editable dialog once the mid-term reminder date has passed", () => {
      renderWithTimeline({
        meetingLogReminderAt: "2026-02-15T06:59:59Z",
        meetingsCompletionDeadlineAt: "2026-04-30T06:59:59Z",
        feedbackDeadlineAt: "2026-05-09T15:59:59Z",
      });
      expect(screen.getByTestId("feedback-dialog")).toHaveAttribute(
        "data-editable",
        "true",
      );
    });

    it("should pass the selected round id and name to the dialog", () => {
      renderWithTimeline({
        meetingLogReminderAt: "2026-02-15T06:59:59Z",
        feedbackDeadlineAt: "2026-05-09T15:59:59Z",
      });
      const dialog = screen.getByTestId("feedback-dialog");
      expect(dialog).toHaveAttribute("data-round-id", "1");
      expect(dialog).toHaveAttribute("data-round-name", "2026 Spring");
    });

    it("should open one month before the meetings deadline when no mid-term reminder is set", () => {
      // Meetings end 2026-03-15, so the window opens 2026-02-15 — already past.
      renderWithTimeline({
        meetingsCompletionDeadlineAt: "2026-03-15T06:59:59Z",
        feedbackDeadlineAt: "2026-05-09T15:59:59Z",
      });
      expect(screen.getByTestId("feedback-dialog")).toBeInTheDocument();
    });

    it("should stay closed when the derived open date is still in the future", () => {
      // Meetings end 2026-04-30, so the window opens 2026-03-30 — not yet.
      renderWithTimeline({
        meetingsCompletionDeadlineAt: "2026-04-30T06:59:59Z",
        feedbackDeadlineAt: "2026-05-09T15:59:59Z",
      });
      expect(screen.queryByTestId("feedback-dialog")).not.toBeInTheDocument();
    });

    it("should render a read-only dialog after the feedback deadline", () => {
      renderWithTimeline({
        meetingLogReminderAt: "2026-01-01T00:00:00Z",
        meetingsCompletionDeadlineAt: "2026-01-20T00:00:00Z",
        feedbackDeadlineAt: "2026-02-01T00:00:00Z",
      });
      expect(screen.getByTestId("feedback-dialog")).toHaveAttribute(
        "data-editable",
        "false",
      );
    });

    it("should close one month after the meetings deadline when no feedback deadline is set", () => {
      // Meetings end 2026-02-10, so the window closes 2026-03-10 — still open.
      renderWithTimeline({
        meetingLogReminderAt: "2026-01-01T00:00:00Z",
        meetingsCompletionDeadlineAt: "2026-02-10T06:59:59Z",
      });
      const dialog = screen.getByTestId("feedback-dialog");
      expect(dialog).toHaveAttribute("data-editable", "true");
      expect(dialog).toHaveAttribute(
        "data-deadline",
        "2026-03-10 14:59 Asia/Shanghai",
      );
    });

    it("should show the deadline in the user's timezone", () => {
      renderWithTimeline({
        meetingLogReminderAt: "2026-02-15T06:59:59Z",
        feedbackDeadlineAt: "2026-05-09T15:59:59Z",
      });
      expect(screen.getByTestId("feedback-dialog")).toHaveAttribute(
        "data-deadline",
        "2026-05-09 23:59 Asia/Shanghai",
      );
    });

    it("should not render the dialog when the user has no participation", () => {
      render(
        <MentorshipParticipantsCard
          {...baseProps}
          participantDetails={{
            roundInfo: {
              ...baseProps.participantDetails.roundInfo,
              timeline: { meetingLogReminderAt: "2026-01-01T00:00:00Z" },
            },
            partnerMeetingOverview: [],
            participantRole: null,
          }}
        />,
      );
      expect(screen.queryByTestId("feedback-dialog")).not.toBeInTheDocument();
    });
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
