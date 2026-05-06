import { renderHook, render, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import { useProfileCompletenessReminder } from "@/pages/Profile/hooks/useProfileCompletenessReminder";

vi.spyOn(toast, "info").mockImplementation(() => {});
vi.spyOn(toast, "dismiss").mockImplementation(() => {});

const PROFILE_SESSION_KEY = "profile-completeness-toast-shown";
const TRAINING_SESSION_KEY = "training-completeness-toast-shown";

const PROFILE_TOAST_ID = "profile-completeness-toast";
const TRAINING_TOAST_ID = "training-completeness-toast";

/**
 * Find the toast.info call whose options carry the given id, render
 * its description JSX, and return both the rendered node and the
 * options object. Returns null when no matching call exists, so tests
 * can assert presence/absence directly.
 */
const findRenderedToast = (toastId) => {
  for (const [title, opts] of toast.info.mock.calls) {
    if (opts?.id !== toastId) continue;
    const { container } = render(opts.description);
    return { title, opts, node: container };
  }
  return null;
};

const completeProfile = {
  isLoading: false,
  personalInfo: {
    firstName: "Jane",
    lastName: "Doe",
    completedTraining: [
      { category: "mentorship_mentor_onboarding", status: "done" },
    ],
  },
  experienceList: [{ id: "exp1" }],
  educationList: [{ id: "edu1" }],
};

describe("useProfileCompletenessReminder", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("does nothing while the profile is still loading", () => {
    renderHook(() =>
      useProfileCompletenessReminder({ ...completeProfile, isLoading: true }),
    );
    expect(toast.info).not.toHaveBeenCalled();
  });

  it("does nothing when nothing is missing", () => {
    renderHook(() => useProfileCompletenessReminder(completeProfile));
    expect(toast.info).not.toHaveBeenCalled();
  });

  describe("profile reminder", () => {
    it("flags Personal Information when firstName is empty", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          personalInfo: {
            ...completeProfile.personalInfo,
            firstName: "",
            lastName: "Doe",
          },
        }),
      );
      const profile = findRenderedToast(PROFILE_TOAST_ID);
      expect(profile).toBeTruthy();
      expect(profile.title).toBe("Complete your profile");
      expect(profile.node.textContent).toContain("Personal Information");
      expect(profile.opts.duration).toBe(Infinity);
      expect(profile.opts.closeButton).toBe(false);
    });

    it("flags Personal Information when lastName is empty", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          personalInfo: {
            ...completeProfile.personalInfo,
            firstName: "Jane",
            lastName: "",
          },
        }),
      );
      expect(findRenderedToast(PROFILE_TOAST_ID).node.textContent).toContain(
        "Personal Information",
      );
    });

    it("does not duplicate Personal Information when both names are empty", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          personalInfo: {
            ...completeProfile.personalInfo,
            firstName: "",
            lastName: "",
          },
        }),
      );
      const occurrences = (
        findRenderedToast(PROFILE_TOAST_ID).node.textContent.match(
          /Personal Information/g,
        ) || []
      ).length;
      expect(occurrences).toBe(1);
    });

    it("flags Experience when experienceList is empty", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          experienceList: [],
        }),
      );
      expect(findRenderedToast(PROFILE_TOAST_ID).node.textContent).toContain(
        "Experience",
      );
    });

    it("flags Education when educationList is empty", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          educationList: [],
        }),
      );
      expect(findRenderedToast(PROFILE_TOAST_ID).node.textContent).toContain(
        "Education",
      );
    });

    it("lists every missing profile section in one toast", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          isLoading: false,
          personalInfo: {
            firstName: "",
            lastName: "",
            completedTraining: [],
          },
          experienceList: [],
          educationList: [],
        }),
      );
      const text = findRenderedToast(PROFILE_TOAST_ID).node.textContent;
      expect(text).toContain("Please fill in: ");
      expect(text).toContain("Personal Information");
      expect(text).toContain("Experience");
      expect(text).toContain("Education");
    });

    it("includes the mentorship-matching rationale", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          experienceList: [],
        }),
      );
      expect(findRenderedToast(PROFILE_TOAST_ID).node.textContent).toMatch(
        /match you with the right partner/i,
      );
    });

    it("does not mention onboarding training in the profile toast", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          personalInfo: {
            ...completeProfile.personalInfo,
            firstName: "",
            completedTraining: [
              { category: "mentorship_mentor_onboarding", status: "to_do" },
            ],
          },
        }),
      );
      expect(
        findRenderedToast(PROFILE_TOAST_ID).node.textContent,
      ).not.toContain("onboarding training");
    });

    it("skips when sessionStorage already records the profile toast was shown", () => {
      sessionStorage.setItem(PROFILE_SESSION_KEY, "1");
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          experienceList: [],
        }),
      );
      expect(findRenderedToast(PROFILE_TOAST_ID)).toBeNull();
    });

    it("writes the sessionStorage marker after firing", () => {
      expect(sessionStorage.getItem(PROFILE_SESSION_KEY)).toBeNull();
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          experienceList: [],
        }),
      );
      expect(sessionStorage.getItem(PROFILE_SESSION_KEY)).toBe("1");
    });
  });

  describe("training reminder", () => {
    const profileWithIncompleteOnboarding = {
      ...completeProfile,
      personalInfo: {
        ...completeProfile.personalInfo,
        completedTraining: [
          { category: "mentorship_mentor_onboarding", status: "to_do" },
        ],
      },
    };

    it("fires when personal info is filled and a mentor onboarding is to_do", () => {
      renderHook(() =>
        useProfileCompletenessReminder(profileWithIncompleteOnboarding),
      );
      const training = findRenderedToast(TRAINING_TOAST_ID);
      expect(training).toBeTruthy();
      expect(training.title).toBe("Complete onboarding training");
      expect(training.node.textContent).toContain(
        "To help you get started smoothly",
      );
      expect(training.opts.duration).toBe(Infinity);
      expect(training.opts.closeButton).toBe(false);
    });

    it("fires when a mentee onboarding is in_progress", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          personalInfo: {
            ...completeProfile.personalInfo,
            completedTraining: [
              {
                category: "mentorship_mentee_onboarding",
                status: "in_progress",
              },
            ],
          },
        }),
      );
      expect(findRenderedToast(TRAINING_TOAST_ID).node.textContent).toContain(
        "To help you get started smoothly",
      );
    });

    it("does not fire while Personal Information is still incomplete", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          ...profileWithIncompleteOnboarding,
          personalInfo: {
            ...profileWithIncompleteOnboarding.personalInfo,
            firstName: "",
          },
        }),
      );
      expect(findRenderedToast(TRAINING_TOAST_ID)).toBeNull();
    });

    it("does not fire for unrelated incomplete categories", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          personalInfo: {
            ...completeProfile.personalInfo,
            completedTraining: [
              { category: "residency_program_onboarding", status: "to_do" },
            ],
          },
        }),
      );
      expect(toast.info).not.toHaveBeenCalled();
    });

    it("skips when sessionStorage already records the training toast was shown", () => {
      sessionStorage.setItem(TRAINING_SESSION_KEY, "1");
      renderHook(() =>
        useProfileCompletenessReminder(profileWithIncompleteOnboarding),
      );
      expect(findRenderedToast(TRAINING_TOAST_ID)).toBeNull();
    });

    it("writes the sessionStorage marker after firing", () => {
      expect(sessionStorage.getItem(TRAINING_SESSION_KEY)).toBeNull();
      renderHook(() =>
        useProfileCompletenessReminder(profileWithIncompleteOnboarding),
      );
      expect(sessionStorage.getItem(TRAINING_SESSION_KEY)).toBe("1");
    });
  });

  describe("both reminders together", () => {
    it("fires the profile and training reminders independently when both apply", () => {
      // Personal info filled (so training fires), but Experience missing
      // (so profile fires too) and onboarding incomplete.
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          experienceList: [],
          personalInfo: {
            ...completeProfile.personalInfo,
            completedTraining: [
              { category: "mentorship_mentor_onboarding", status: "to_do" },
            ],
          },
        }),
      );
      expect(toast.info).toHaveBeenCalledTimes(2);
      const profile = findRenderedToast(PROFILE_TOAST_ID);
      const training = findRenderedToast(TRAINING_TOAST_ID);
      expect(profile).toBeTruthy();
      expect(training).toBeTruthy();
      expect(profile.node.textContent).toContain("Experience");
      expect(training.node.textContent).toContain("onboarding training");
      expect(sessionStorage.getItem(PROFILE_SESSION_KEY)).toBe("1");
      expect(sessionStorage.getItem(TRAINING_SESSION_KEY)).toBe("1");
    });

    it("dismissing one toast does not suppress the other on the next visit", () => {
      // Simulate a prior session where only the training toast was
      // dismissed (its session key is set). Profile data still has
      // missing pieces — the profile toast should still fire.
      sessionStorage.setItem(TRAINING_SESSION_KEY, "1");
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          experienceList: [],
          personalInfo: {
            ...completeProfile.personalInfo,
            completedTraining: [
              { category: "mentorship_mentor_onboarding", status: "to_do" },
            ],
          },
        }),
      );
      expect(findRenderedToast(PROFILE_TOAST_ID)).toBeTruthy();
      expect(findRenderedToast(TRAINING_TOAST_ID)).toBeNull();
    });
  });

  describe("toast layout", () => {
    it("renders the body text with a confirm button that dismisses the toast", () => {
      renderHook(() =>
        useProfileCompletenessReminder({
          ...completeProfile,
          experienceList: [],
        }),
      );
      const profile = findRenderedToast(PROFILE_TOAST_ID);
      const confirmButton = profile.node.querySelector("button");
      expect(confirmButton.textContent).toBe("Confirm");
      fireEvent.click(confirmButton);
      expect(toast.dismiss).toHaveBeenCalledWith(PROFILE_TOAST_ID);
    });
  });
});
