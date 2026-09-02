import { render, screen, fireEvent, act } from "@testing-library/react";
import { toast } from "sonner";
import { deleteMeeting, rescheduleMeeting } from "@/api/meetingApi";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import MentorshipParticipantsCard from "@/pages/PersonalDashboard/components/MentorshipParticipantsCard";
import { MentorshipRoundStatus } from "@/constants/MentorshipRoundStatus";

const { mockUseFlags } = vi.hoisted(() => ({
  mockUseFlags: vi.fn(),
}));

vi.mock("@/hooks/useFeatureFlags", () => ({
  useFeatureFlags: mockUseFlags,
}));

vi.mock("@/api/meetingApi", () => ({
  deleteMeeting: vi.fn(),
  rescheduleMeeting: vi.fn(),
}));

vi.mock("@/pages/PersonalDashboard/components/MeetingManagementDialog", () => ({
  default: ({
    roundId,
    canSchedule,
    scheduleUnavailableReason,
    canLogPast,
    logPartnerId,
    logUnavailableReason,
    userTimezone,
    onLogged,
  }) => (
    <div
      data-testid="meeting-dialog"
      data-round-id={String(roundId)}
      data-can-schedule={String(canSchedule)}
      data-schedule-unavailable={scheduleUnavailableReason ?? ""}
      data-can-log-past={String(canLogPast)}
      data-log-partner-id={String(logPartnerId)}
      data-log-unavailable={logUnavailableReason ?? ""}
      data-user-timezone={userTimezone}
    >
      <button onClick={onLogged}>mock-logged</button>
    </div>
  ),
}));

vi.mock("@/pages/PersonalDashboard/components/MeetingOverviewCard", () => ({
  default: ({
    overview,
    canManageMeetings,
    onDeleteMeeting,
    onRescheduleMeeting,
  }) => (
    <div
      data-testid={`overview-${overview.partnerId}`}
      data-can-manage={String(canManageMeetings)}
    >
      <button
        onClick={() => onDeleteMeeting({ meetingId: "m-1" })}
      >{`mock-cancel-${overview.partnerId}`}</button>
      <button
        onClick={() => onRescheduleMeeting({ meetingId: "m-1" })}
      >{`mock-reschedule-${overview.partnerId}`}</button>
    </div>
  ),
}));

// The dialog has its own suite; here only the slot it hands back matters.
vi.mock("@/pages/PersonalDashboard/components/MeetingRescheduleDialog", () => ({
  default: ({ open, onSubmit }) =>
    open ? (
      <button
        onClick={() =>
          onSubmit({
            date: "2026-06-08",
            startTime: "09:30",
            durationMinutes: 60,
            timezone: "Asia/Shanghai",
          })
        }
      >
        mock-reschedule-submit
      </button>
    ) : null,
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
        isActive: true,
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
    mockUseFlags.mockReturnValue({
      "manual-submit-meeting": true,
      "create-google-meeting": true,
    });
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

  it("should offer logging a past meeting to mentees", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-can-log-past",
      "true",
    );
  });

  it("should NOT offer logging to mentors", () => {
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          ...baseProps.participantDetails,
          participantRole: "mentor",
        }}
      />,
    );
    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-can-log-past",
      "false",
    );
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

  it("should pass the viewer's timezone to the meeting dialog", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-user-timezone",
      "Asia/Shanghai",
    );
  });

  it("should pass the partner to log against", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-log-partner-id",
      "1",
    );
  });

  it("should pass the selected round to the meeting dialog", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-round-id",
      "1",
    );
  });

  it("should withhold logging while more than one partner is shown", () => {
    // The log form is one per round, so it can only name a partner while there
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
              isActive: true,
            },
          ],
        }}
      />,
    );

    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-log-unavailable",
      "No single active pairing to log a meeting against.",
    );
  });

  const endedPairing = {
    partnerId: 2,
    preferredName: "Bob",
    requiredMeetings: 3,
    completedCount: 3,
    completedRate: 100,
    meetingTimeList: [],
    participantRole: "mentee",
    isActive: false,
  };

  it("should label a pairing that has ended", () => {
    // The partner left the round. The meetings held with them are still this
    // user's participation, so the row stays and says why it is not current.
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          ...baseProps.participantDetails,
          partnerMeetingOverview: [endedPairing],
        }}
      />,
    );

    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(screen.getByText("Ended")).toBeInTheDocument();
    expect(
      screen.queryByText(/have not participated/i),
    ).not.toBeInTheDocument();
  });

  it("should not label a live pairing", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);

    expect(screen.queryByText("Ended")).not.toBeInTheDocument();
  });

  it("should withhold logging when the only pairing has ended", () => {
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          ...baseProps.participantDetails,
          partnerMeetingOverview: [endedPairing],
        }}
      />,
    );

    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-log-unavailable",
      "No single active pairing to log a meeting against.",
    );
  });

  it("should log against the live pairing when an ended one is also shown", () => {
    // Changing mentor mid-round leaves both pairings on the card. Only one of
    // them is current, so the target is not ambiguous and submitting stays
    // available.
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          ...baseProps.participantDetails,
          partnerMeetingOverview: [
            ...baseProps.participantDetails.partnerMeetingOverview,
            endedPairing,
          ],
        }}
      />,
    );

    const dialog = screen.getByTestId("meeting-dialog");
    expect(dialog).toHaveAttribute("data-log-unavailable", "");
    expect(dialog).toHaveAttribute("data-log-partner-id", "1");
  });

  it("should render a MeetingOverviewCard for each partner", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    expect(screen.getByTestId("overview-1")).toBeInTheDocument();
  });

  it("should offer cancelling on the same flag that gates booking", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);
    expect(screen.getByTestId("overview-1")).toHaveAttribute(
      "data-can-manage",
      "true",
    );
  });

  it("should NOT offer cancelling when the google meeting flag is off", () => {
    mockUseFlags.mockReturnValue({
      "manual-submit-meeting": true,
      "create-google-meeting": false,
    });

    render(<MentorshipParticipantsCard {...baseProps} />);
    expect(screen.getByTestId("overview-1")).toHaveAttribute(
      "data-can-manage",
      "false",
    );
  });

  it("should cancel against the selected round and that partner, then refresh", async () => {
    const refreshMeetings = vi.fn();
    deleteMeeting.mockResolvedValue({});
    const successToast = vi
      .spyOn(toast, "success")
      .mockImplementation(() => {});

    render(
      <MentorshipParticipantsCard
        {...baseProps}
        refreshMeetings={refreshMeetings}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "mock-cancel-1" }));
    });

    expect(deleteMeeting).toHaveBeenCalledWith("m-1", "1", 1);
    expect(refreshMeetings).toHaveBeenCalled();
    expect(successToast).toHaveBeenCalled();
    successToast.mockRestore();
  });

  it("should surface a failed cancellation and leave the list alone", async () => {
    const refreshMeetings = vi.fn();
    deleteMeeting.mockRejectedValue(new Error("boom"));
    const errorToast = vi.spyOn(toast, "error").mockImplementation(() => {});
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <MentorshipParticipantsCard
        {...baseProps}
        refreshMeetings={refreshMeetings}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "mock-cancel-1" }));
    });

    expect(errorToast).toHaveBeenCalled();
    expect(refreshMeetings).not.toHaveBeenCalled();
    errorToast.mockRestore();
    consoleSpy.mockRestore();
  });

  it("should open the reschedule dialog without calling the API", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);

    expect(
      screen.queryByRole("button", { name: "mock-reschedule-submit" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "mock-reschedule-1" }));

    expect(
      screen.getByRole("button", { name: "mock-reschedule-submit" }),
    ).toBeInTheDocument();
    expect(rescheduleMeeting).not.toHaveBeenCalled();
  });

  it("should reschedule against the selected round and that partner, then refresh", async () => {
    const refreshMeetings = vi.fn();
    rescheduleMeeting.mockResolvedValue({});
    const successToast = vi
      .spyOn(toast, "success")
      .mockImplementation(() => {});

    render(
      <MentorshipParticipantsCard
        {...baseProps}
        refreshMeetings={refreshMeetings}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "mock-reschedule-1" }));
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: "mock-reschedule-submit" }),
      );
    });

    // `round_id` is passed through as the prop's own type; the DTO coerces.
    expect(rescheduleMeeting).toHaveBeenCalledWith("m-1", {
      round_id: "1",
      partner_id: 1,
      timezone: "Asia/Shanghai",
      start_date: "2026-06-08",
      start_time: "09:30",
      duration_minutes: 60,
    });
    expect(refreshMeetings).toHaveBeenCalled();
    expect(successToast).toHaveBeenCalled();
    successToast.mockRestore();
  });

  it("should surface a failed reschedule and leave the list alone", async () => {
    const refreshMeetings = vi.fn();
    rescheduleMeeting.mockRejectedValue(new Error("boom"));
    const errorToast = vi.spyOn(toast, "error").mockImplementation(() => {});
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <MentorshipParticipantsCard
        {...baseProps}
        refreshMeetings={refreshMeetings}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "mock-reschedule-1" }));
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: "mock-reschedule-submit" }),
      );
    });

    expect(errorToast).toHaveBeenCalled();
    expect(refreshMeetings).not.toHaveBeenCalled();
    errorToast.mockRestore();
    consoleSpy.mockRestore();
  });

  it("should reschedule against the partner whose row the control came from, not just the first partner", async () => {
    // With a single partner, threading the wrong (e.g. loop-stale) partner id
    // through would still pass every other reschedule test. A second partner
    // is what makes that mistake observable.
    const secondPartner = {
      partnerId: 2,
      preferredName: "Bob",
      requiredMeetings: 3,
      completedCount: 0,
      completedRate: 0,
      meetingTimeList: [],
      participantRole: "mentee",
      isActive: true,
    };
    rescheduleMeeting.mockResolvedValue({});

    render(
      <MentorshipParticipantsCard
        {...baseProps}
        participantDetails={{
          ...baseProps.participantDetails,
          partnerMeetingOverview: [
            ...baseProps.participantDetails.partnerMeetingOverview,
            secondPartner,
          ],
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "mock-reschedule-2" }));
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: "mock-reschedule-submit" }),
      );
    });

    expect(rescheduleMeeting).toHaveBeenCalledWith(
      "m-1",
      expect.objectContaining({ partner_id: 2 }),
    );
  });

  it("should call refreshMeetings after a meeting is logged", () => {
    const refreshMeetings = vi.fn();

    render(
      <MentorshipParticipantsCard
        {...baseProps}
        refreshMeetings={refreshMeetings}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "mock-logged" }));
    expect(refreshMeetings).toHaveBeenCalled();
  });

  it("should NOT offer logging when the manual submit flag is off", () => {
    mockUseFlags.mockReturnValue({
      "manual-submit-meeting": false,
      "create-google-meeting": true,
    });
    render(<MentorshipParticipantsCard {...baseProps} />);

    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-can-log-past",
      "false",
    );
  });

  it("should offer scheduling when the google meeting flag is on", () => {
    render(<MentorshipParticipantsCard {...baseProps} />);

    const dialog = screen.getByTestId("meeting-dialog");
    expect(dialog).toHaveAttribute("data-can-schedule", "true");
    expect(dialog).toHaveAttribute("data-schedule-unavailable", "");
  });

  it("should NOT offer scheduling when the google meeting flag is off", () => {
    mockUseFlags.mockReturnValue({
      "manual-submit-meeting": true,
      "create-google-meeting": false,
    });
    render(<MentorshipParticipantsCard {...baseProps} />);

    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-can-schedule",
      "false",
    );
  });

  it("should match the selected round regardless of whether the id is a string or a number", () => {
    // The round selector hands back a string; the round list carries numbers.
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        selectedRoundId="20"
        roundSelectionData={{
          sortedRounds: [
            { id: 10, name: "2025 Fall", status: "completed" },
            { id: 20, name: "2026 Spring", status: "active" },
          ],
        }}
      />,
    );

    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-schedule-unavailable",
      "",
    );
  });

  it("should say why scheduling is unavailable when the selected round is not active", () => {
    render(
      <MentorshipParticipantsCard
        {...baseProps}
        roundSelectionData={{
          sortedRounds: [{ id: "1", name: "2026 Spring", status: "completed" }],
        }}
      />,
    );

    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-schedule-unavailable",
      "No active mentorship round",
    );
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

  it("should keep logging available when the deadline is in the future", () => {
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
    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-log-unavailable",
      "",
    );
  });

  it("should close logging when the deadline is well in the past", () => {
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
    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-log-unavailable",
      "Logging meetings for this round has closed.",
    );
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

  it("should close logging when the round is completed without a deadline", () => {
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

    expect(screen.getByTestId("meeting-dialog")).toHaveAttribute(
      "data-log-unavailable",
      "Logging meetings for this round has closed.",
    );
  });
});
