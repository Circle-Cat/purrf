import { renderHook } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import { useProfileCompletenessReminder } from "@/pages/Profile/hooks/useProfileCompletenessReminder";

vi.spyOn(toast, "info").mockImplementation(() => {});

const SESSION_KEY = "profile-completeness-toast-shown";

const completeProfile = {
  isLoading: false,
  personalInfo: { firstName: "Jane", lastName: "Doe" },
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

  it("does nothing when all three sections are filled", () => {
    renderHook(() => useProfileCompletenessReminder(completeProfile));
    expect(toast.info).not.toHaveBeenCalled();
  });

  it("flags Personal Information when firstName is empty", () => {
    renderHook(() =>
      useProfileCompletenessReminder({
        ...completeProfile,
        personalInfo: { firstName: "", lastName: "Doe" },
      }),
    );
    expect(toast.info).toHaveBeenCalledOnce();
    const [title, opts] = toast.info.mock.calls[0];
    expect(title).toBe("Complete your profile");
    expect(opts.description).toContain("Personal Information");
    expect(opts.duration).toBe(Infinity);
  });

  it("flags Personal Information when lastName is empty", () => {
    renderHook(() =>
      useProfileCompletenessReminder({
        ...completeProfile,
        personalInfo: { firstName: "Jane", lastName: "" },
      }),
    );
    expect(toast.info).toHaveBeenCalledOnce();
    expect(toast.info.mock.calls[0][1].description).toContain(
      "Personal Information",
    );
  });

  it("does not duplicate Personal Information when both names are empty", () => {
    renderHook(() =>
      useProfileCompletenessReminder({
        ...completeProfile,
        personalInfo: { firstName: "", lastName: "" },
      }),
    );
    const description = toast.info.mock.calls[0][1].description;
    const occurrences = (description.match(/Personal Information/g) || [])
      .length;
    expect(occurrences).toBe(1);
  });

  it("flags Experience when experienceList is empty", () => {
    renderHook(() =>
      useProfileCompletenessReminder({
        ...completeProfile,
        experienceList: [],
      }),
    );
    expect(toast.info).toHaveBeenCalledOnce();
    expect(toast.info.mock.calls[0][1].description).toContain("Experience");
  });

  it("flags Education when educationList is empty", () => {
    renderHook(() =>
      useProfileCompletenessReminder({
        ...completeProfile,
        educationList: [],
      }),
    );
    expect(toast.info).toHaveBeenCalledOnce();
    expect(toast.info.mock.calls[0][1].description).toContain("Education");
  });

  it("lists every missing section in one toast when multiple are empty", () => {
    renderHook(() =>
      useProfileCompletenessReminder({
        isLoading: false,
        personalInfo: { firstName: "", lastName: "" },
        experienceList: [],
        educationList: [],
      }),
    );
    expect(toast.info).toHaveBeenCalledOnce();
    const description = toast.info.mock.calls[0][1].description;
    expect(description).toContain("Personal Information");
    expect(description).toContain("Experience");
    expect(description).toContain("Education");
  });

  it("includes the mentorship-matching rationale in the toast description", () => {
    renderHook(() =>
      useProfileCompletenessReminder({
        ...completeProfile,
        experienceList: [],
      }),
    );
    const description = toast.info.mock.calls[0][1].description;
    expect(description).toMatch(/match you with the right partner/i);
  });

  it("skips the toast when sessionStorage already records it was shown", () => {
    sessionStorage.setItem(SESSION_KEY, "1");
    renderHook(() =>
      useProfileCompletenessReminder({
        ...completeProfile,
        experienceList: [],
      }),
    );
    expect(toast.info).not.toHaveBeenCalled();
  });

  it("writes the sessionStorage marker after firing", () => {
    expect(sessionStorage.getItem(SESSION_KEY)).toBeNull();
    renderHook(() =>
      useProfileCompletenessReminder({
        ...completeProfile,
        experienceList: [],
      }),
    );
    expect(sessionStorage.getItem(SESSION_KEY)).toBe("1");
  });
});
