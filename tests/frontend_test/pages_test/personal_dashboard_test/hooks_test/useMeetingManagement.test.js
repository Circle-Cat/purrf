import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useMeetingManagement } from "@/pages/PersonalDashboard/hooks/useMeetingManagement";
import { getMyMentorshipPartners } from "@/api/mentorshipApi";
import { postMyMentorshipMeetingV2 } from "@/api/meetingApi";

vi.mock("@/api/mentorshipApi", () => ({
  getMyMentorshipPartners: vi.fn(),
}));

vi.mock("@/api/meetingApi", () => ({
  postMyMentorshipMeetingV2: vi.fn(),
}));

describe("useMeetingManagement Hook Unit Tests", () => {
  const mockRoundId = "round-1";

  const mockPartnersResponse = {
    data: [
      {
        id: 99,
        firstName: "Zhang",
        lastName: "San",
        preferredName: "San",
        email: "zhangsan@example.com",
      },
      {
        id: 100,
        firstName: "Li",
        lastName: "Si",
        preferredName: "",
        email: "lisi@example.com",
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    getMyMentorshipPartners.mockResolvedValue(mockPartnersResponse);
  });

  describe("Initial Data Fetching (fetchPageData)", () => {
    it("should return an empty map and not trigger any API requests when roundId is missing", async () => {
      const { result } = renderHook(() => useMeetingManagement(null));

      expect(result.current.partners).toBeInstanceOf(Map);
      expect(result.current.partners.size).toBe(0);
      expect(getMyMentorshipPartners).not.toHaveBeenCalled();
    });

    it("should call the Partners API and key the map by partner id", async () => {
      const { result } = renderHook(() => useMeetingManagement(mockRoundId));

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(getMyMentorshipPartners).toHaveBeenCalledWith(mockRoundId);

      expect(result.current.partners.size).toBe(2);
      expect(result.current.partners.has("99")).toBe(true);
      expect(result.current.partners.get("99")).toEqual(
        mockPartnersResponse.data[0],
      );
    });

    it("should handle corrupt/partial response items from backend cleanly without throwing", async () => {
      getMyMentorshipPartners.mockResolvedValue({
        data: [null, { id: null }, { id: 99, email: "zhangsan@example.com" }],
      });

      const { result } = renderHook(() => useMeetingManagement(mockRoundId));
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.partners.size).toBe(1);
      expect(result.current.partners.has("99")).toBe(true);
    });

    it("should gracefully stop loading and log an error when API request fails", async () => {
      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      getMyMentorshipPartners.mockRejectedValue(
        new Error("Partners API Fetch Failed"),
      );

      const { result } = renderHook(() => useMeetingManagement(mockRoundId));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        "Failed to fetch mentorship partners",
        expect.any(Error),
      );
      consoleSpy.mockRestore();
    });

    it("should completely abort state distribution if the component unmounts mid-flight", async () => {
      let triggerResolution;
      getMyMentorshipPartners.mockImplementation(
        () =>
          new Promise((res) => {
            triggerResolution = res;
          }),
      );

      const { result, unmount } = renderHook(() =>
        useMeetingManagement(mockRoundId),
      );

      unmount();

      await act(async () => {
        triggerResolution(mockPartnersResponse);
      });

      expect(result.current.partners.size).toBe(0);
    });
  });

  describe("Create a meeting(postMyMentorshipMeetingV2)", () => {
    it("should call the post API, return its data, and refresh the partners after success", async () => {
      postMyMentorshipMeetingV2.mockResolvedValue({
        data: { created: [{ meetingId: "g-1" }], failed: [] },
      });
      const { result } = renderHook(() => useMeetingManagement(mockRoundId));
      await waitFor(() => expect(result.current.isLoading).toBe(false));
      vi.clearAllMocks();
      getMyMentorshipPartners.mockResolvedValue(mockPartnersResponse);

      const payload = { round_id: mockRoundId, partner_id: 1 };
      let returned;
      await act(async () => {
        returned = await result.current.bookMeeting(payload);
      });

      expect(postMyMentorshipMeetingV2).toHaveBeenCalledWith(payload);
      expect(returned).toEqual({ created: [{ meetingId: "g-1" }], failed: [] });
      expect(getMyMentorshipPartners).toHaveBeenCalledTimes(1);
    });

    it("should log to console and throw error to be caught by the caller when Creating fails", async () => {
      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mockErr = new Error("Booking Server Error");
      postMyMentorshipMeetingV2.mockRejectedValue(mockErr);

      const { result } = renderHook(() => useMeetingManagement(mockRoundId));
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await expect(result.current.bookMeeting({})).rejects.toThrow(
        "Booking Server Error",
      );
      expect(consoleSpy).toHaveBeenCalledWith("Book meeting failed:", mockErr);

      consoleSpy.mockRestore();
    });
  });
});
