import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import PersonalDashboard from "@/pages/PersonalDashboard";
import { useMentorshipData } from "@/pages/PersonalDashboard/hooks/useMentorshipData";
import { useAuth } from "@/context/auth";
import { useWorkActivityData } from "@/pages/PersonalDashboard/hooks/useWorkActivityData";
import { useMyApplications } from "@/pages/PersonalDashboard/hooks/useMyApplications";
import { PERMISSIONS } from "@/constants/Permissions";
import { MentorshipRoundStatus } from "@/constants/MentorshipRoundStatus";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";

vi.mock("@/pages/PersonalDashboard/components/MentorshipInfoBanner", () => ({
  default: vi.fn(({ registration, isRegistrationOpen }) => (
    <div data-testid="mock-banner">
      Banner - {isRegistrationOpen ? "Open" : "Closed"} - {registration?.status}
    </div>
  )),
}));

vi.mock("@/pages/PersonalDashboard/hooks/useMentorshipData", () => ({
  useMentorshipData: vi.fn(),
}));

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/pages/PersonalDashboard/hooks/useWorkActivityData", () => ({
  useWorkActivityData: vi.fn(),
}));

vi.mock("@/pages/PersonalDashboard/hooks/useMyApplications", () => ({
  useMyApplications: vi.fn(),
}));

vi.mock("@/pages/PersonalDashboard/components/MyApplicationsCard", () => ({
  default: () => (
    <div data-testid="mock-my-applications-card">Applications</div>
  ),
}));

vi.mock("@/pages/PersonalDashboard/components/WorkActivityDataCard", () => ({
  WorkActivityDataCard: (props) => (
    <div data-testid="work-activity-card">
      <button disabled={props.isLoading}>Mock Work Card</button>
    </div>
  ),
}));

vi.mock(
  "@/pages/PersonalDashboard/components/MentorshipParticipantsCard",
  () => ({
    default: () => (
      <div data-testid="mock-participants-card">Participants Card</div>
    ),
  }),
);

vi.mock("@/pages/PersonalDashboard/components/GoogleMeetingControl", () => ({
  GoogleMeetingControl: vi.fn(({ meetingRoundId }) => (
    <div data-testid="mock-manage-meetings-btn">
      Mock Button - Round: {meetingRoundId ?? "null"}
    </div>
  )),
}));

vi.mock("@/hooks/useFeatureFlags", () => {
  return {
    useFeatureFlags: vi.fn(),
  };
});

describe("PersonalDashboard", () => {
  const mockHookData = {
    registration: { id: "reg-1", status: "PENDING" },
    isRegistrationOpen: true,
    isFeedbackEnabled: false,
    saveRegistration: vi.fn(),
    pastPartners: [],
    isPartnersLoading: false,
    loadPastPartners: vi.fn(),
    isLoading: false,
    selectedRoundId: null,
    roundSelectionData: {
      sortedRounds: [{ id: 1, status: MentorshipRoundStatus.COMPLETED }],
    },
  };

  const defaultWorkActivityMock = {
    summary: {},
    isPersonalSummaryLoading: false,
    fetchPersonalSummary: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useMentorshipData.mockReturnValue(mockHookData);
    useWorkActivityData.mockReturnValue(defaultWorkActivityMock);
    useMyApplications.mockReturnValue({
      applications: [],
      isLoading: false,
      loadError: false,
      load: vi.fn(),
      hasHiredMentorshipApplication: true,
    });
    useAuth.mockReturnValue({ permissions: [] });
    vi.mocked(useFeatureFlags).mockReturnValue({
      [FEATURE_FLAGS.CREATE_GOOGLE_MEETING]: true,
    });
  });

  it("renders the welcome header", () => {
    render(<PersonalDashboard />);

    expect(screen.getByText("Welcome")).toBeInTheDocument();
  });

  it("renders the clapping hands emoji", () => {
    render(<PersonalDashboard />);

    const emoji = screen.getByRole("img", {
      name: /clapping hands/i,
    });

    expect(emoji).toBeInTheDocument();
  });

  it("renders the welcome header layout container", () => {
    render(<PersonalDashboard />);

    const header = screen.getByText("Welcome").closest("div");
    expect(header).toBeTruthy();
  });

  it("passes hook data to MentorshipInfoBanner", () => {
    useMentorshipData.mockReturnValue({
      ...mockHookData,
      isRegistrationOpen: true,
      registration: { status: "SUCCESS" },
    });

    render(<PersonalDashboard />);

    // Verify that the mocked child component received the correct props
    // and rendered the expected content
    const banner = screen.getByTestId("mock-banner");
    expect(banner.innerHTML).toContain("Open");
    expect(banner.innerHTML).toContain("SUCCESS");
  });

  it("passes the correct state to the banner when registration is closed", () => {
    useMentorshipData.mockReturnValue({
      ...mockHookData,
      isRegistrationOpen: false,
      registration: null,
    });

    render(<PersonalDashboard />);

    const banner = screen.getByTestId("mock-banner");
    expect(banner.innerHTML).toContain("Closed");
  });

  it("keeps the layout structure intact even when data is loading", () => {
    useMentorshipData.mockReturnValue({
      ...mockHookData,
      isLoading: true, // simulate loading state
    });

    render(<PersonalDashboard />);

    // The welcome header should still be rendered
    expect(screen.getByText("Welcome")).toBeDefined();
    // The banner should still be rendered
    expect(screen.getByTestId("mock-banner")).toBeDefined();
  });

  it("shows work activity card for internal users", () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ],
    });

    useWorkActivityData.mockReturnValue({
      summary: {},
      isPersonalSummaryLoading: false,
      fetchPersonalSummary: vi.fn(),
    });

    render(<PersonalDashboard />);

    expect(screen.getByTestId("work-activity-card")).toBeInTheDocument();
  });

  it("does not show work activity card for non internal users", () => {
    useAuth.mockReturnValue({
      permissions: [],
    });

    useWorkActivityData.mockReturnValue({
      summary: {},
      isPersonalSummaryLoading: false,
      fetchPersonalSummary: vi.fn(),
    });

    render(<PersonalDashboard />);

    expect(screen.queryByTestId("work-activity-card")).toBeNull();
  });

  it("disables work activity card search button while loading for internal users", () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ],
    });

    useWorkActivityData.mockReturnValue({
      summary: {},
      isPersonalSummaryLoading: true,
      fetchPersonalSummary: vi.fn(),
    });

    render(<PersonalDashboard />);

    const cardContainer = screen.getByTestId("work-activity-card");
    const button = cardContainer.querySelector("button");

    expect(button).toBeDisabled();
  });

  describe("Manage Meetings Button", () => {
    it("calculates active meetingRoundId using enum and passes it to the button", () => {
      useMentorshipData.mockReturnValue({
        ...mockHookData,
        selectedRoundId: 20,
        roundSelectionData: {
          sortedRounds: [
            { id: 10, status: MentorshipRoundStatus.COMPLETED },
            { id: 20, status: MentorshipRoundStatus.ACTIVE },
          ],
        },
      });

      render(<PersonalDashboard />);

      const btn = screen.getByTestId("mock-manage-meetings-btn");
      expect(btn).toBeInTheDocument();
      expect(btn.innerHTML).toContain("Round: 20");
    });

    it("successfully activates and casts ID when selectedRoundId is a string from select dropdown", () => {
      useMentorshipData.mockReturnValue({
        ...mockHookData,
        selectedRoundId: "20",
        roundSelectionData: {
          sortedRounds: [
            { id: 10, status: MentorshipRoundStatus.COMPLETED },
            { id: 20, status: MentorshipRoundStatus.ACTIVE },
          ],
        },
      });

      render(<PersonalDashboard />);

      const btn = screen.getByTestId("mock-manage-meetings-btn");
      expect(btn).toBeInTheDocument();
      expect(btn.innerHTML).toContain("Round: 20");
    });

    it("passes null to the button when the user selects a completed / inactive round", () => {
      useMentorshipData.mockReturnValue({
        ...mockHookData,
        selectedRoundId: 10,
        roundSelectionData: {
          sortedRounds: [
            { id: 10, status: MentorshipRoundStatus.COMPLETED },
            { id: 20, status: MentorshipRoundStatus.ACTIVE },
          ],
        },
      });

      render(<PersonalDashboard />);

      const btn = screen.getByTestId("mock-manage-meetings-btn");
      expect(btn.innerHTML).toContain("Round: null");
    });

    it("passes null to the button when there is no active round", () => {
      useMentorshipData.mockReturnValue({
        ...mockHookData,
        selectedRoundId: 10,
        roundSelectionData: {
          sortedRounds: [{ id: 10, status: MentorshipRoundStatus.COMPLETED }],
        },
      });

      render(<PersonalDashboard />);

      const btn = screen.getByTestId("mock-manage-meetings-btn");
      expect(btn.innerHTML).toContain("Round: null");
    });
  });

  it("always renders the My Applications card", () => {
    render(<PersonalDashboard />);
    expect(screen.getByTestId("mock-my-applications-card")).toBeInTheDocument();
  });

  it("shows the mentorship banner and participants card when hasHiredMentorshipApplication is true", () => {
    useMyApplications.mockReturnValue({
      applications: [],
      isLoading: false,
      loadError: false,
      load: vi.fn(),
      hasHiredMentorshipApplication: true,
    });

    render(<PersonalDashboard />);

    expect(screen.getByTestId("mock-banner")).toBeInTheDocument();
    expect(screen.getByTestId("mock-participants-card")).toBeInTheDocument();
  });

  it("hides the mentorship banner and participants card when hasHiredMentorshipApplication is false", () => {
    useMyApplications.mockReturnValue({
      applications: [],
      isLoading: false,
      loadError: false,
      load: vi.fn(),
      hasHiredMentorshipApplication: false,
    });

    render(<PersonalDashboard />);

    expect(screen.queryByTestId("mock-banner")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("mock-participants-card"),
    ).not.toBeInTheDocument();
  });

  it("passes hasHiredMentorshipApplication as the enabled option to useMentorshipData", () => {
    useMyApplications.mockReturnValue({
      applications: [],
      isLoading: false,
      loadError: false,
      load: vi.fn(),
      hasHiredMentorshipApplication: false,
    });

    render(<PersonalDashboard />);

    expect(useMentorshipData).toHaveBeenCalledWith({ enabled: false });
  });
});
