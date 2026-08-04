import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useMeetingManagement } from "@/pages/PersonalDashboard/hooks/useMeetingManagement";
import { getMyMentorshipPartners } from "@/api/mentorshipApi";
import {
  getMyMentorshipMeetingsV2,
  postMyMentorshipMeetingV2,
  deleteMeeting,
  batchDeleteMeetings,
} from "@/api/meetingApi";

vi.mock("@/api/mentorshipApi", () => ({
  getMyMentorshipPartners: vi.fn(),
}));

vi.mock("@/api/meetingApi", () => ({
  getMyMentorshipMeetingsV2: vi.fn(),
  postMyMentorshipMeetingV2: vi.fn(),
  deleteMeeting: vi.fn(),
  batchDeleteMeetings: vi.fn(),
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

  const mockMeetingsResponse = {
    data: {
      meetingInfo: [
        {
          partnerId: 99,
          participantRole: "Mentor",
          meetingTimeList: [
            {
              meetingId: "m-1",
              startDatetime: "2026-06-01T10:00:00Z",
              endDatetime: "2026-06-01T11:00:00Z",
              isCompleted: false,
            },
            {
              meetingId: "m-2",
              startDatetime: "2026-06-01T11:00:00Z",
              endDatetime: "2026-06-01T12:00:00Z",
              isCompleted: true,
            },
          ],
        },
        {
          partnerId: 100,
          participantRole: "Mentee",
          meetingTimeList: [
            {
              meetingId: "m-3",
              startDatetime: "2026-06-02T14:00:00Z",
              endDatetime: "2026-06-02T15:00:00Z",
              isCompleted: false,
            },
          ],
        },
      ],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    getMyMentorshipPartners.mockResolvedValue(mockPartnersResponse);
    getMyMentorshipMeetingsV2.mockResolvedValue(mockMeetingsResponse);
  });

  describe("Initial Data Fetching (fetchPageData)", () => {
    it("should return empty arrays and not trigger any API requests when roundId is missing", async () => {
      const { result } = renderHook(() => useMeetingManagement(null));

      expect(result.current.upcomingMeetings).toEqual([]);
      expect(result.current.partners).toBeInstanceOf(Map);
      expect(result.current.partners.size).toBe(0);
      expect(getMyMentorshipMeetingsV2).not.toHaveBeenCalled();
    });

    it("should concurrently call V2 and Partners APIs, and correctly merge and flatten uncompleted meetings", async () => {
      const { result } = renderHook(() => useMeetingManagement(mockRoundId));

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(getMyMentorshipMeetingsV2).toHaveBeenCalledWith({
        roundId: mockRoundId,
        includeDetails: false,
      });
      expect(getMyMentorshipPartners).toHaveBeenCalledWith(mockRoundId);

      expect(result.current.partners.size).toBe(2);
      expect(result.current.partners.has("99")).toBe(true);
      expect(result.current.partners.get("99")).toEqual(
        mockPartnersResponse.data[0],
      );

      expect(result.current.upcomingMeetings).toHaveLength(2);

      expect(result.current.upcomingMeetings[0]).toEqual({
        meetingId: "m-1",
        partnerId: 99,
        partnerRole: "Mentor",
        partnerName: "San",
        partnerEmail: "zhangsan@example.com",
        startDatetime: "2026-06-01T10:00:00Z",
        endDatetime: "2026-06-01T11:00:00Z",
      });

      expect(result.current.upcomingMeetings[1]).toEqual({
        meetingId: "m-3",
        partnerId: 100,
        partnerRole: "Mentee",
        partnerName: "Li Si",
        partnerEmail: "lisi@example.com",
        startDatetime: "2026-06-02T14:00:00Z",
        endDatetime: "2026-06-02T15:00:00Z",
      });
    });

    it("should handle corrupt/partial response items from backend cleanly without throwing", async () => {
      const corruptMeetingsResponse = {
        data: {
          meetingInfo: [
            null,
            { partnerId: null, meetingTimeList: [] },
            {
              partnerId: 99,
              meetingTimeList: [
                null,
                { meetingId: "m-valid", isCompleted: false },
              ],
            },
          ],
        },
      };
      getMyMentorshipMeetingsV2.mockResolvedValue(corruptMeetingsResponse);

      const { result } = renderHook(() => useMeetingManagement(mockRoundId));
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.upcomingMeetings).toHaveLength(1);
      expect(result.current.upcomingMeetings[0].meetingId).toBe("m-valid");
    });

    it("should gracefully degrade partnerName to 'Unknown' if no matching partner info is found", async () => {
      getMyMentorshipPartners.mockResolvedValue({ data: [] });

      const { result } = renderHook(() => useMeetingManagement(mockRoundId));
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.upcomingMeetings[0].partnerName).toBe("Unknown");
      expect(result.current.upcomingMeetings[0].partnerEmail).toBe("");
    });

    it("should gracefully stop loading and log an error when API request fails", async () => {
      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      getMyMentorshipMeetingsV2.mockRejectedValue(
        new Error("V2 API Fetch Failed"),
      );

      const { result } = renderHook(() => useMeetingManagement(mockRoundId));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        "Failed to fetch meeting log",
        expect.any(Error),
      );
      consoleSpy.mockRestore();
    });

    it("should completely abort state distribution if the component unmounts mid-flight", async () => {
      let triggerResolution;
      getMyMentorshipMeetingsV2.mockImplementation(
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
        triggerResolution(mockMeetingsResponse);
      });

      expect(result.current.upcomingMeetings).toEqual([]);
    });
  });

  describe("Create a meeting(postMyMentorshipMeetingV2)", () => {
    it("should call the post API, return its data, and refresh the list after success", async () => {
      postMyMentorshipMeetingV2.mockResolvedValue({
        data: { created: [{ meetingId: "g-1" }], failed: [] },
      });
      const { result } = renderHook(() => useMeetingManagement(mockRoundId));
      await waitFor(() => expect(result.current.isLoading).toBe(false));
      vi.clearAllMocks();

      const payload = { round_id: mockRoundId, partner_id: 1 };
      let returned;
      await act(async () => {
        returned = await result.current.bookMeeting(payload);
      });

      expect(postMyMentorshipMeetingV2).toHaveBeenCalledWith(payload);
      expect(returned).toEqual({ created: [{ meetingId: "g-1" }], failed: [] });
      expect(getMyMentorshipMeetingsV2).toHaveBeenCalledTimes(1);
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

  describe("Canceling Meetings", () => {
    it("should return early and not trigger any delete APIs when invalid or empty arrays are provided", async () => {
      const { result } = renderHook(() => useMeetingManagement(mockRoundId));
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.cancelMeetings([]);
        await result.current.cancelMeetings(null);
      });

      expect(deleteMeeting).not.toHaveBeenCalled();
      expect(batchDeleteMeetings).not.toHaveBeenCalled();
    });

    it("should route to single delete API (deleteMeeting) when canceling exactly 1 meeting", async () => {
      deleteMeeting.mockResolvedValue({ success: true });
      const { result } = renderHook(() => useMeetingManagement(mockRoundId));

      await waitFor(() => expect(result.current.isLoading).toBe(false));
      vi.clearAllMocks();

      const singleSelection = [{ meetingId: "m-1", partnerId: 99 }];

      await act(async () => {
        await result.current.cancelMeetings(singleSelection);
      });

      expect(deleteMeeting).toHaveBeenCalledWith("m-1", mockRoundId, 99);
      expect(batchDeleteMeetings).not.toHaveBeenCalled();
      expect(getMyMentorshipMeetingsV2).toHaveBeenCalledTimes(1);
    });

    it("should group meetings by partnerId and payload them to batchDeleteMeetings when canceling multiple meetings", async () => {
      batchDeleteMeetings.mockResolvedValue({ success: true });
      const { result } = renderHook(() => useMeetingManagement(mockRoundId));

      await waitFor(() => expect(result.current.isLoading).toBe(false));
      vi.clearAllMocks();

      const multipleSelections = [
        { meetingId: "m-1", partnerId: 99 },
        { meetingId: "m-2", partnerId: 99 },
        { meetingId: "m-3", partnerId: 100 },
      ];

      await act(async () => {
        await result.current.cancelMeetings(multipleSelections);
      });

      expect(deleteMeeting).not.toHaveBeenCalled();
      expect(batchDeleteMeetings).toHaveBeenCalledWith([
        {
          roundId: mockRoundId,
          partnerId: 99,
          meetingIds: ["m-1", "m-2"],
        },
        {
          roundId: mockRoundId,
          partnerId: 100,
          meetingIds: ["m-3"],
        },
      ]);
      expect(getMyMentorshipMeetingsV2).toHaveBeenCalledTimes(1);
    });

    it("should throw error to the parent UI layer for toast notification when cancelMeetings API encounters a failure", async () => {
      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mockErr = new Error("Delete Request Failed");
      deleteMeeting.mockRejectedValue(mockErr);

      const { result } = renderHook(() => useMeetingManagement(mockRoundId));
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      const singleSelection = [{ meetingId: "m-1", partnerId: 99 }];

      await expect(
        result.current.cancelMeetings(singleSelection),
      ).rejects.toThrow("Delete Request Failed");
      expect(consoleSpy).toHaveBeenCalledWith(
        "Cancel meetings failed:",
        mockErr,
      );

      consoleSpy.mockRestore();
    });

    it("should safely overlook malformed items in selection array during evaluation", async () => {
      batchDeleteMeetings.mockResolvedValue({ success: true });
      const { result } = renderHook(() => useMeetingManagement(mockRoundId));

      await waitFor(() => expect(result.current.isLoading).toBe(false));
      vi.clearAllMocks();

      await act(async () => {
        await result.current.cancelMeetings([
          null,
          { meetingId: "m-1" },
          { meetingId: "m-2", partnerId: 99 },
          { meetingId: "m-3", partnerId: 99 },
        ]);
      });

      expect(batchDeleteMeetings).toHaveBeenCalledWith([
        { roundId: mockRoundId, partnerId: 99, meetingIds: ["m-2", "m-3"] },
      ]);
    });
  });
});
