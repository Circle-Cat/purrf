import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useProfileData } from "@/pages/Profile/hooks/useProfileData";
import { getMyProfile, updateMyProfile } from "@/api/profileApi";
import {
  parseDateParts,
  getDaysSince,
  sortExperienceOrEducationList,
} from "@/pages/Profile/utils";

vi.mock("@/api/profileApi", () => ({
  getMyProfile: vi.fn(),
  updateMyProfile: vi.fn(),
}));

vi.mock("@/pages/Profile/utils", () => ({
  parseDateParts: vi.fn(),
  getDaysSince: vi.fn(),
  sortExperienceOrEducationList: vi.fn(),
}));

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
        alternativeEmails: ["john@alt.com"],
        communicationMethod: "google_chat",
        updatedTimestamp: "2023-01-01T00:00:00Z",
      },
      experience: [
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
          degree: "BS",
          startDate: "2016-01",
          endDate: "2020-01",
        },
        // Second education entry
        {
          id: "edu2",
          school: "Uni B",
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
     * Verify email merging logic (primary + alternative).
     */
    expect(personalInfo.emails).toHaveLength(2);
    expect(personalInfo.emails[0]).toEqual({
      id: "primary",
      email: "john@primary.com",
      isPrimary: true,
    });
    expect(personalInfo.emails[1]).toMatchObject({
      email: "john@alt.com",
      isPrimary: false,
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

    /**
     * Verify that the sort function was actually utilized.
     * Since both lists have >1 item, sort should be called at least twice.
     */
    expect(sortExperienceOrEducationList).toHaveBeenCalled();
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

  describe("Computed Property: canEditPersonalInfo", () => {
    it("should allow edit if updatedTimestamp is null", async () => {
      const noTimeProfile = {
        profile: {
          ...mockProfileResponse.profile,
          user: {
            ...mockProfileResponse.profile.user,
            updatedTimestamp: null,
          },
        },
      };
      getMyProfile.mockResolvedValue({ data: noTimeProfile });

      const { result } = renderHook(() => useProfileData());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.canEditPersonalInfo).toBe(true);
    });

    it("should NOT allow edit if less than 30 days since update", async () => {
      getMyProfile.mockResolvedValue({ data: mockProfileResponse });

      /**
       * Mock a recent update (10 days ago).
       */
      getDaysSince.mockReturnValue(10);

      const { result } = renderHook(() => useProfileData());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.canEditPersonalInfo).toBe(false);
      expect(getDaysSince).toHaveBeenCalledWith(
        mockProfileResponse.profile.user.updatedTimestamp,
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

      expect(result.current.canEditPersonalInfo).toBe(true);
    });
  });

  describe("Computed Property: nextEditableDate", () => {
    it("should return a formatted date 30 days from updatedTimestamp", async () => {
      getMyProfile.mockResolvedValue({ data: mockProfileResponse });

      const { result } = renderHook(() => useProfileData());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      const expectedDate = new Date("2023-01-01T00:00:00Z");
      expectedDate.setDate(expectedDate.getDate() + 30);

      expect(result.current.nextEditableDate).toBe(
        expectedDate.toLocaleDateString(),
      );
    });
  });
});
