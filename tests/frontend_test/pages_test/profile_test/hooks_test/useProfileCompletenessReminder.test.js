import { renderHook, render, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import { useProfileCompletenessReminder } from "@/pages/Profile/hooks/useProfileCompletenessReminder";

vi.spyOn(toast, "info").mockImplementation(() => {});
vi.spyOn(toast, "dismiss").mockImplementation(() => {});

const PROFILE_SESSION_KEY = "profile-completeness-toast-shown";

const PROFILE_TOAST_ID = "profile-completeness-toast";

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

  it("does not nag when the profile failed to load", () => {
    // Empty data that WOULD normally fire the profile reminder, but the
    // emptiness is a load failure — not a genuinely incomplete profile.
    renderHook(() =>
      useProfileCompletenessReminder({
        isLoading: false,
        loadError: true,
        personalInfo: { completedTraining: [] },
        experienceList: [],
        educationList: [],
      }),
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

  it("never fires a training reminder, even with an incomplete onboarding", () => {
    // The training reminder now lives on the Personal Dashboard, where a
    // newly admitted participant will actually see it.
    renderHook(() =>
      useProfileCompletenessReminder({
        isLoading: false,
        loadError: false,
        personalInfo: {
          firstName: "Ada",
          lastName: "Lovelace",
          completedTraining: [
            { category: "mentorship_mentee_onboarding", status: "to_do" },
          ],
        },
        experienceList: [{ id: 1 }],
        educationList: [{ id: 1 }],
      }),
    );

    expect(toast.info).not.toHaveBeenCalled();
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
