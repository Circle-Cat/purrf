import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useProfileData } from "@/pages/Profile/hooks/useProfileData";
import { getMyProfile, updateMyProfile } from "@/api/profileApi";
import {
  parseDateParts,
  sortExperienceOrEducationList,
  DegreeEnum,
} from "@/pages/Profile/utils";
import { getDaysSince, formatLocalYmd } from "@/utils/dateTime";

vi.mock("@/api/profileApi", () => ({
  getMyProfile: vi.fn(),
  updateMyProfile: vi.fn(),
}));

vi.mock("@/pages/Profile/utils", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    parseDateParts: vi.fn(),
    sortExperienceOrEducationList: vi.fn(),
  };
});

vi.mock("@/utils/dateTime", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    getDaysSince: vi.fn(),
  };
});

describe("useProfileData Hook", () => {
  /**
   * Mocked backend profile response used across test cases.
   */
  const mockProfileResponse = {
    profile: {
      user: {
        id: "u123",
        firstName: "John",
        lastName: "Doe",
        primaryEmail: "john@primary.com",
        communicationMethod: "google_chat",
        timezone: "America/Los_Angeles",
        timezoneUpdatedAt: "2023-01-01T00:00:00Z",
      },
      workHistory: [
        {
          id: "exp1",
          title: "Dev",
          companyOrOrganization: "Tech Corp",
          startDate: "2020-01",
          endDate: "2021-01",
          isCurrentJob: false,
        },
        // Second experience entry
        {
          id: "exp2",
          title: "Senior Dev",
          companyOrOrganization: "StartUp Inc",
          startDate: "2022-01",
          endDate: "2023-01",
          isCurrentJob: true,
        },
      ],
      education: [
        {
          id: "edu1",
          school: "Uni A",
          // Valid degree value that exists in DegreeEnum
          degree: "Bachelor",
          startDate: "2016-01",
          endDate: "2020-01",
        },
        // Second education entry
        {
          id: "edu2",
          school: "Uni B",
          // Invalid degree value NOT defined in DegreeEnum, should be mapped to empty string
          degree: "MS",
          startDate: "2020-09",
          endDate: "2022-06",
        },
      ],
      training: [],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    parseDateParts.mockReturnValue({ month: "01", year: "2020" });
    getDaysSince.mockReturnValue(0);
    sortExperienceOrEducationList.mockReturnValue(0);
  });

  it("should initialize with default loading state", () => {
    /**
     * Keep the API call pending to verify the initial loading state.
     */
    getMyProfile.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useProfileData());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.personalInfo.emails).toEqual([]);
    expect(result.current.experienceList).toEqual([]);
    expect(result.current.educationList).toEqual([]);
  });

  it("should fetch data and map it correctly to state", async () => {
    getMyProfile.mockResolvedValue({ data: mockProfileResponse });
    parseDateParts.mockReturnValue({ month: "05", year: "2023" });

    const { result } = renderHook(() => useProfileData());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const { personalInfo } = result.current;
    expect(personalInfo.firstName).toBe("John");
    expect(personalInfo.title).toBe("Senior Dev");

    /**
     * Verify email list holds only the primary email; alternative emails are
     * no longer surfaced on the profile.
     */
    expect(personalInfo.emails).toHaveLength(1);
    expect(personalInfo.emails[0]).toEqual({
      id: "primary",
      email: "john@primary.com",
      isPrimary: true,
    });

    /**
     * Verify experience field remapping and list processing.
     * We expect 2 items based on the mock response.
     */
    expect(result.current.experienceList).toHaveLength(2);
    expect(result.current.experienceList[0]).toMatchObject({
      company: "Tech Corp",
      title: "Dev",
      startMonth: "05",
    });

    /**
     * Verify education field remapping and list processing.
     * We expect 2 items based on the mock response.
     */
    expect(result.current.educationList).toHaveLength(2);
    expect(result.current.educationList[0]).toMatchObject({
      institution: "Uni A",
    });
    expect(result.current.educationList[1]).toMatchObject({
      institution: "Uni B",
    });
    expect(result.current.educationList[0]).toMatchObject({
      degree: DegreeEnum.Bachelor,
    });
    expect(result.current.educationList[1]).toMatchObject({
      degree: "",
    });
    /**
     * Verify that the sort function was actually utilized.
     * Since both lists have >1 item, sort should be called at least twice.
     */
    expect(sortExperienceOrEducationList).toHaveBeenCalled();
  });

  it("should map training records keyed on category (not name)", async () => {
    const profileWithTraining = {
      profile: {
        ...mockProfileResponse.profile,
        training: [
          {
            id: 32,
            category: "mentorship_mentee_onboarding",
            completedTimestamp: "1970-01-01T00:00:00Z",
            status: "to_do",
            deadline: "2026-05-18T06:59:00Z",
            link: null,
          },
        ],
      },
    };
    getMyProfile.mockResolvedValue({ data: profileWithTraining });

    const { result } = renderHook(() => useProfileData());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const [training] = result.current.personalInfo.completedTraining;
    expect(training.id).toBe(32);
    expect(training.category).toBe("mentorship_mentee_onboarding");
    expect(training.status).toBe("to_do");
    expect(training.link).toBeNull();
    // The pre-fix mapping read t.name (which the API never returns), so the
    // mapped object had `name: undefined`. Lock the rename in.
    expect(training).not.toHaveProperty("name");
    // Raw API timestamps pass through unchanged so TrainingSection can
    // format the actual day, not just month/year.
    expect(training.completedTimestamp).toBe("1970-01-01T00:00:00Z");
    expect(training.deadline).toBe("2026-05-18T06:59:00Z");
    expect(training).not.toHaveProperty("completionMonth");
    expect(training).not.toHaveProperty("dueMonth");
  });

  it("should handle API errors gracefully", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    getMyProfile.mockRejectedValue(new Error("Network Error"));

    const { result } = renderHook(() => useProfileData());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    /**
     * Ensure the hook does not crash and keeps default state.
     */
    expect(result.current.personalInfo.id).toBeUndefined();

    consoleSpy.mockRestore();
  });

  describe("handleUpdateProfile", () => {
    it("should call update API and update local state on success", async () => {
      getMyProfile.mockResolvedValue({ data: mockProfileResponse });

      const updatedResponse = {
        profile: {
          ...mockProfileResponse.profile,
          user: {
            ...mockProfileResponse.profile.user,
            firstName: "Jane",
          },
        },
      };
      updateMyProfile.mockResolvedValue({ data: updatedResponse });

      const { result } = renderHook(() => useProfileData());
      await waitFor(() => expect(result.current.isLoading).toBe(false));
      await act(async () => {
        await result.current.handleUpdateProfile({
          firstName: "Jane",
        });
      });

      expect(updateMyProfile).toHaveBeenCalledWith({
        firstName: "Jane",
      });
      expect(result.current.personalInfo.firstName).toBe("Jane");
    });
  });

  describe("Computed Property: canEditTimezone", () => {
    it("should allow edit if timezoneUpdatedAt is null", async () => {
      const noTimeProfile = {
        profile: {
          ...mockProfileResponse.profile,
          user: {
            ...mockProfileResponse.profile.user,
            timezoneUpdatedAt: null,
          },
        },
      };
      getMyProfile.mockResolvedValue({ data: noTimeProfile });

      const { result } = renderHook(() => useProfileData());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.canEditTimezone).toBe(true);
    });

    it("should NOT allow edit if less than 30 days since update", async () => {
      getMyProfile.mockResolvedValue({ data: mockProfileResponse });

      /**
       * Mock a recent update (10 days ago).
       */
      getDaysSince.mockReturnValue(10);

      const { result } = renderHook(() => useProfileData());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.canEditTimezone).toBe(false);
      expect(getDaysSince).toHaveBeenCalledWith(
        mockProfileResponse.profile.user.timezoneUpdatedAt,
      );
    });

    it("should allow edit if 30 days or more since update", async () => {
      getMyProfile.mockResolvedValue({ data: mockProfileResponse });

      /**
       * Mock exactly 30 days since last update.
       */
      getDaysSince.mockReturnValue(30);

      const { result } = renderHook(() => useProfileData());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.canEditTimezone).toBe(true);
    });
  });

  describe("Computed Property: nextEditableDate", () => {
    it("should return a formatted date 30 days from timezoneUpdatedAt", async () => {
      getMyProfile.mockResolvedValue({ data: mockProfileResponse });

      const { result } = renderHook(() => useProfileData());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      const expectedDate = new Date("2023-01-01T00:00:00Z");
      expectedDate.setDate(expectedDate.getDate() + 30);

      expect(result.current.nextEditableDate).toBe(
        formatLocalYmd(expectedDate),
      );
    });
  });
});
