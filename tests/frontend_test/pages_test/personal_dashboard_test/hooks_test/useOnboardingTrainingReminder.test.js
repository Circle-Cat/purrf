import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { useOnboardingTrainingReminder } from "@/pages/PersonalDashboard/hooks/useOnboardingTrainingReminder";
import * as profileApi from "@/api/profileApi";
import * as reminderToast from "@/components/common/showReminderToast";

vi.mock("@/api/profileApi");

const withTraining = (training) => ({ data: { training } });

describe("useOnboardingTrainingReminder", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    vi.spyOn(reminderToast, "showReminderToast").mockImplementation(() => {});
  });

  it("does not fetch while disabled", () => {
    renderHook(() => useOnboardingTrainingReminder({ enabled: false }));

    expect(profileApi.getMyProfile).not.toHaveBeenCalled();
  });

  it("requests only the training section", async () => {
    profileApi.getMyProfile.mockResolvedValue(withTraining([]));

    renderHook(() => useOnboardingTrainingReminder({ enabled: true }));

    await waitFor(() =>
      expect(profileApi.getMyProfile).toHaveBeenCalledWith({
        fields: ["training"],
      }),
    );
  });

  it("fires the reminder for an incomplete onboarding", async () => {
    profileApi.getMyProfile.mockResolvedValue(
      withTraining([
        { id: 1, category: "mentorship_mentee_onboarding", status: "to_do" },
      ]),
    );

    renderHook(() => useOnboardingTrainingReminder({ enabled: true }));

    await waitFor(() =>
      expect(reminderToast.showReminderToast).toHaveBeenCalledTimes(1),
    );
    const call = reminderToast.showReminderToast.mock.calls[0][0];
    expect(call.title).toBe("Complete onboarding training");
    expect(call.message).toMatch(/Profile page/);
  });

  it("does not fire once the onboarding is done", async () => {
    profileApi.getMyProfile.mockResolvedValue(
      withTraining([
        { id: 1, category: "mentorship_mentee_onboarding", status: "done" },
      ]),
    );

    renderHook(() => useOnboardingTrainingReminder({ enabled: true }));

    await waitFor(() => expect(profileApi.getMyProfile).toHaveBeenCalled());
    expect(reminderToast.showReminderToast).not.toHaveBeenCalled();
  });

  it("ignores unrelated incomplete training categories", async () => {
    profileApi.getMyProfile.mockResolvedValue(
      withTraining([
        { id: 1, category: "corporate_culture_course", status: "to_do" },
      ]),
    );

    renderHook(() => useOnboardingTrainingReminder({ enabled: true }));

    await waitFor(() => expect(profileApi.getMyProfile).toHaveBeenCalled());
    expect(reminderToast.showReminderToast).not.toHaveBeenCalled();
  });

  it("fires without waiting for the user to fill in their name", async () => {
    // Deliberate change from the old Profile-page reminder: an admitted
    // participant with an empty profile is exactly who needs this.
    profileApi.getMyProfile.mockResolvedValue(
      withTraining([
        { id: 1, category: "mentorship_mentor_onboarding", status: "to_do" },
      ]),
    );

    renderHook(() => useOnboardingTrainingReminder({ enabled: true }));

    await waitFor(() =>
      expect(reminderToast.showReminderToast).toHaveBeenCalledTimes(1),
    );
  });

  it("fires at most once per session", async () => {
    profileApi.getMyProfile.mockResolvedValue(
      withTraining([
        { id: 1, category: "mentorship_mentee_onboarding", status: "to_do" },
      ]),
    );

    const first = renderHook(() =>
      useOnboardingTrainingReminder({ enabled: true }),
    );
    await waitFor(() =>
      expect(reminderToast.showReminderToast).toHaveBeenCalledTimes(1),
    );
    first.unmount();

    renderHook(() => useOnboardingTrainingReminder({ enabled: true }));
    await waitFor(() =>
      expect(profileApi.getMyProfile).toHaveBeenCalledTimes(1),
    );
    expect(reminderToast.showReminderToast).toHaveBeenCalledTimes(1);
  });

  it("stays silent when the fetch fails", async () => {
    profileApi.getMyProfile.mockRejectedValue(new Error("network error"));

    renderHook(() => useOnboardingTrainingReminder({ enabled: true }));

    await waitFor(() => expect(profileApi.getMyProfile).toHaveBeenCalled());
    expect(reminderToast.showReminderToast).not.toHaveBeenCalled();
  });
});
