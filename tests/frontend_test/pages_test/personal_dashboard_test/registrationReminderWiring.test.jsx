import { render, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import PersonalDashboard from "@/pages/PersonalDashboard";
import { useAuth } from "@/context/auth";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { useWorkActivityData } from "@/pages/PersonalDashboard/hooks/useWorkActivityData";
import * as mentorshipApi from "@/api/mentorshipApi";
import * as recruitingApi from "@/api/recruitingApi";
import * as meetingApi from "@/api/meetingApi";
import * as profileApi from "@/api/profileApi";
import * as reminderToast from "@/components/common/showReminderToast";

// Everything below the hooks is stubbed; the hooks themselves are the
// subject, so `useMyApplications`, `useMentorshipData` and
// `useRegistrationReminder` all run for real against mocked endpoints.
vi.mock("@/api/mentorshipApi");
vi.mock("@/api/recruitingApi");
vi.mock("@/api/meetingApi");
vi.mock("@/api/profileApi");

vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));
vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));
vi.mock("@/pages/PersonalDashboard/hooks/useWorkActivityData", () => ({
  useWorkActivityData: vi.fn(),
}));

vi.mock("@/pages/PersonalDashboard/components/MentorshipInfoBanner", () => ({
  default: () => <div data-testid="mock-banner" />,
}));
vi.mock("@/pages/PersonalDashboard/components/MyApplicationsCard", () => ({
  default: () => <div data-testid="mock-my-applications-card" />,
}));
vi.mock("@/pages/PersonalDashboard/components/WorkActivityDataCard", () => ({
  WorkActivityDataCard: () => <div data-testid="work-activity-card" />,
}));
vi.mock(
  "@/pages/PersonalDashboard/components/MentorshipParticipantsCard",
  () => ({ default: () => <div data-testid="mock-participants-card" /> }),
);
const OPEN_ROUND = {
  id: 7,
  name: "2026 Fall",
  timeline: {
    promotionStartAt: "2026-08-01T00:00:00Z",
    mentorApplicationDeadlineAt: "2026-09-30T06:59:59Z",
    menteeApplicationDeadlineAt: "2026-09-30T06:59:59Z",
    meetingsCompletionDeadlineAt: "2026-12-01T00:00:00Z",
    feedbackDeadlineAt: "2026-12-15T00:00:00Z",
  },
};

const toastTitles = () =>
  reminderToast.showReminderToast.mock.calls.map((c) => c[0].title);

describe("PersonalDashboard registration reminder wiring", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    vi.spyOn(reminderToast, "showReminderToast").mockImplementation(() => {});

    useAuth.mockReturnValue({ permissions: [] });
    useFeatureFlags.mockReturnValue({});
    useWorkActivityData.mockReturnValue({
      summary: {},
      isPersonalSummaryLoading: false,
      fetchPersonalSummary: vi.fn(),
    });

    // The admission arrives from the network, so the mentorship hooks
    // start out disabled and are switched on a tick later — the ordering
    // the page actually runs in.
    recruitingApi.listMyApplications.mockResolvedValue({
      data: {
        applications: [
          {
            applicationId: 1,
            jobId: 2,
            jobTitle: "Mentorship",
            jobKind: "activity",
            mentorshipRole: "mentee",
            stage: "hired",
          },
        ],
        mentorshipRoles: ["mentee"],
      },
    });
    profileApi.getMyProfile.mockResolvedValue({
      data: { profile: { training: [{ id: 1 }] } },
    });
    mentorshipApi.getAllMentorshipRounds.mockResolvedValue({
      data: [OPEN_ROUND],
    });
    mentorshipApi.getMyMentorshipRegistration.mockResolvedValue({
      data: { isRegistered: false },
    });
    mentorshipApi.getMyMentorshipPartners.mockResolvedValue({ data: [] });
    mentorshipApi.getMyMentorshipMeetingLog.mockResolvedValue({ data: {} });
    mentorshipApi.getMyMentorshipMatchResult.mockResolvedValue({ data: null });
    meetingApi.getMyMentorshipMeetingsV2.mockResolvedValue({ data: {} });
  });

  it("never announces a closed registration while a round is open", async () => {
    // The admission resolving switches the mentorship hooks on. Until
    // that fetch answers, the mentorship data is still at its initial
    // state -- no open round, no deadline -- which is not an answer.
    render(<PersonalDashboard />);

    await waitFor(() =>
      expect(reminderToast.showReminderToast).toHaveBeenCalled(),
    );

    expect(toastTitles()).not.toContain("Mentorship registration");
    expect(toastTitles()).toContain("Register for 2026 Fall");
  });

  it("still says so when registration really has not opened", async () => {
    mentorshipApi.getAllMentorshipRounds.mockResolvedValue({ data: [] });

    render(<PersonalDashboard />);

    await waitFor(() =>
      expect(toastTitles()).toContain("Mentorship registration"),
    );
  });
});
