import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import PersonalDashboard from "@/pages/PersonalDashboard";
import MentorshipInfoBanner from "@/pages/PersonalDashboard/components/MentorshipInfoBanner";
import { useMentorshipData } from "@/pages/PersonalDashboard/hooks/useMentorshipData";
import { useAuth } from "@/context/auth";
import { useWorkActivityData } from "@/pages/PersonalDashboard/hooks/useWorkActivityData";
import { useMyApplications } from "@/hooks/useMyApplications";
import { PERMISSIONS } from "@/constants/Permissions";
import { MentorshipRoundStatus } from "@/constants/MentorshipRoundStatus";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import * as profileApi from "@/api/profileApi";

vi.mock("@/api/profileApi", () => ({ getMyProfile: vi.fn() }));

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

vi.mock("@/hooks/useMyApplications", () => ({
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

vi.mock("@/hooks/useFeatureFlags", () => {
  return {
    useFeatureFlags: vi.fn(),
  };
});

describe("PersonalDashboard", () => {
  const mockHookData = {
    registration: { id: "reg-1", status: "PENDING" },
    isRegistrationOpen: true,
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
    profileApi.getMyProfile.mockResolvedValue({
      data: { profile: { training: [] } },
    });
    useMentorshipData.mockReturnValue(mockHookData);
    useWorkActivityData.mockReturnValue(defaultWorkActivityMock);
    useMyApplications.mockReturnValue({
      applications: [],
      isLoading: false,
      loadError: false,
      load: vi.fn(),
      hiredMentorshipRoles: ["mentee"],
    });
    useAuth.mockReturnValue({ permissions: [] });
    vi.mocked(useFeatureFlags).mockReturnValue({
      [FEATURE_FLAGS.CREATE_GOOGLE_MEETING]: true,
    });
  });

  it("loads mentorship data for the roles the user was admitted as", () => {
    render(<PersonalDashboard />);

    expect(useMentorshipData).toHaveBeenCalledWith({
      enabled: true,
      hiredMentorshipRoles: ["mentee"],
    });
  });

  describe("mentorship banner wiring", () => {
    const lastBannerProps = () => MentorshipInfoBanner.mock.calls.at(-1)[0];

    it("hands the banner the registration round, its deadline and the viewer's zone", () => {
      const roundSelectionData = { sortedRounds: [{ id: 42 }] };
      useMentorshipData.mockReturnValue({
        ...mockHookData,
        regRoundId: 42,
        regRoundName: "2027 Spring",
        registrationDeadlineAt: "2027-01-20T03:00:00Z",
        roundSelectionData,
        userTimezone: "Asia/Tokyo",
      });

      render(<PersonalDashboard />);

      expect(lastBannerProps()).toMatchObject({
        regRoundId: 42,
        regRoundName: "2027 Spring",
        registrationDeadlineAt: "2027-01-20T03:00:00Z",
        roundSelectionData,
        userTimezone: "Asia/Tokyo",
      });
    });

    it("holds the banner back until the training status has loaded", async () => {
      profileApi.getMyProfile.mockResolvedValue({
        data: {
          profile: {
            training: [
              {
                id: 3,
                category: "mentorship_mentee_onboarding",
                status: "done",
              },
            ],
          },
        },
      });

      render(<PersonalDashboard />);

      expect(MentorshipInfoBanner.mock.calls[0][0].isLoading).toBe(true);
      await waitFor(() => expect(lastBannerProps().isLoading).toBe(false));
      expect(lastBannerProps().isTrainingDone).toBe(true);
      expect(profileApi.getMyProfile).toHaveBeenCalledWith({
        fields: ["training"],
      });
    });

    it("reads the onboarding course of the registered role, not the admitted one", async () => {
      useMentorshipData.mockReturnValue({
        ...mockHookData,
        registration: { isRegistered: true },
        registeredRole: "mentor",
      });
      profileApi.getMyProfile.mockResolvedValue({
        data: {
          profile: {
            training: [
              {
                id: 3,
                category: "mentorship_mentee_onboarding",
                status: "done",
              },
              {
                id: 4,
                category: "mentorship_mentor_onboarding",
                status: "in_progress",
              },
            ],
          },
        },
      });

      render(<PersonalDashboard />);

      await waitFor(() => expect(lastBannerProps().isLoading).toBe(false));
      expect(lastBannerProps().isTrainingDone).toBe(false);
    });

    it("holds the banner back while the mentorship data is loading", () => {
      useMentorshipData.mockReturnValue({ ...mockHookData, isLoading: true });

      render(<PersonalDashboard />);

      expect(lastBannerProps().isLoading).toBe(true);
    });

    it("does not fetch training for someone with no mentorship admission", () => {
      useMyApplications.mockReturnValue({
        applications: [],
        isLoading: false,
        loadError: false,
        load: vi.fn(),
        hiredMentorshipRoles: [],
      });

      render(<PersonalDashboard />);

      expect(profileApi.getMyProfile).not.toHaveBeenCalled();
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

  it("hides the mentorship section when there is no hired mentorship role", () => {
    useMyApplications.mockReturnValue({
      applications: [],
      isLoading: false,
      loadError: false,
      load: vi.fn(),
      hiredMentorshipRoles: [],
    });

    render(<PersonalDashboard />);

    expect(
      screen.queryByTestId("mock-participants-card"),
    ).not.toBeInTheDocument();
  });

  it("always renders the My Applications card", () => {
    render(<PersonalDashboard />);
    expect(screen.getByTestId("mock-my-applications-card")).toBeInTheDocument();
  });

  it("shows the mentorship banner and participants card once a hired mentorship role resolves", () => {
    useMyApplications.mockReturnValue({
      applications: [],
      isLoading: false,
      loadError: false,
      load: vi.fn(),
      hiredMentorshipRoles: ["mentor"],
    });

    render(<PersonalDashboard />);

    expect(screen.getByTestId("mock-banner")).toBeInTheDocument();
    expect(screen.getByTestId("mock-participants-card")).toBeInTheDocument();
  });

  it("hides the mentorship banner and participants card while applications are still loading", () => {
    useMyApplications.mockReturnValue({
      applications: [],
      isLoading: true,
      loadError: false,
      load: vi.fn(),
      hiredMentorshipRoles: [],
    });

    render(<PersonalDashboard />);

    expect(screen.queryByTestId("mock-banner")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("mock-participants-card"),
    ).not.toBeInTheDocument();
  });

  it("hides the mentorship banner and participants card when the applications fetch errored", () => {
    useMyApplications.mockReturnValue({
      applications: [],
      isLoading: false,
      loadError: true,
      load: vi.fn(),
      hiredMentorshipRoles: [],
    });

    render(<PersonalDashboard />);

    expect(screen.queryByTestId("mock-banner")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("mock-participants-card"),
    ).not.toBeInTheDocument();
  });

  it("hides the mentorship banner and participants card when there is no hired mentorship role", () => {
    useMyApplications.mockReturnValue({
      applications: [],
      isLoading: false,
      loadError: false,
      load: vi.fn(),
      hiredMentorshipRoles: [],
    });

    render(<PersonalDashboard />);

    expect(screen.queryByTestId("mock-banner")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("mock-participants-card"),
    ).not.toBeInTheDocument();
  });

  it("passes showMentorshipSection as the enabled option to useMentorshipData", () => {
    useMyApplications.mockReturnValue({
      applications: [],
      isLoading: false,
      loadError: false,
      load: vi.fn(),
      hiredMentorshipRoles: [],
    });

    render(<PersonalDashboard />);

    expect(useMentorshipData).toHaveBeenCalledWith({
      enabled: false,
      hiredMentorshipRoles: [],
    });
  });

  it("passes the per-role registration entries through to MentorshipInfoBanner", () => {
    const registrationEntries = [
      { role: "mentor", deadlineAt: "2026-09-30T15:59:00Z", isOpen: true },
    ];
    const loadRegistrationForRole = vi.fn();
    useMentorshipData.mockReturnValue({
      ...mockHookData,
      registrationEntries,
      registeredRole: null,
      loadRegistrationForRole,
    });

    render(<PersonalDashboard />);

    // React 19 calls function components as (props, undefined); toHaveBeenCalledWith's
    // expect.anything() rejects that literal undefined second arg, so assert on the
    // first call's props directly instead.
    expect(MentorshipInfoBanner.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        registrationEntries,
        registeredRole: null,
        loadRegistrationForRole,
      }),
    );
  });

  it("spaces the dashboard cards vertically", () => {
    const { container } = render(<PersonalDashboard />);
    expect(container.querySelector(".personal-dashboard").className).toContain(
      "space-y-5",
    );
  });
});
