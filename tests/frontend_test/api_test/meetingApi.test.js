import { vi, describe, it, expect, beforeEach } from "vitest";
import request from "@/utils/request";
import {
  deleteMeeting,
  batchDeleteMeetings,
  getMyMentorshipMeetingsV2,
  postMyMentorshipMeetingV2,
} from "@/api/meetingApi";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

vi.mock("@/utils/request", () => {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
      delete: vi.fn(),
    },
  };
});

const assertErrorPropagation = async (apiCallFn) => {
  const mockAxiosError = {
    message: "Network Error",
    response: { status: 500, data: "Internal Server Error" },
  };

  request.get.mockRejectedValue(mockAxiosError);
  request.post.mockRejectedValue(mockAxiosError);
  request.delete.mockRejectedValue(mockAxiosError);

  await expect(apiCallFn()).rejects.toEqual(mockAxiosError);
};

describe("Meeting Management Service API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("deleteMeeting", () => {
    it("should call the correct DELETE endpoint with route and query parameters", async () => {
      const mockMeetingId = "abc123";
      const mockRoundId = 1;
      const mockPartnerId = 42;
      const mockResponse = { success: true };

      request.delete.mockResolvedValue(mockResponse);

      const result = await deleteMeeting(
        mockMeetingId,
        mockRoundId,
        mockPartnerId,
      );

      const expectedUrl =
        API_ENDPOINTS.MENTORSHIP_MEETING_V2_SINGLE(mockMeetingId);

      expect(request.delete).toHaveBeenCalledWith(expectedUrl, {
        params: {
          round_id: mockRoundId,
          partner_id: mockPartnerId,
        },
      });
      expect(result).toEqual(mockResponse);
    });

    it("should propagate complex network errors upward securely", async () => {
      await assertErrorPropagation(() => deleteMeeting("abc123", 1, 42));
    });
  });

  describe("batchDeleteMeetings", () => {
    it("should call the correct POST endpoint with the grouped deletions payload", async () => {
      const mockDeletions = [
        {
          round_id: 1,
          partner_id: 42,
          meeting_ids: ["abc123", "def456"],
        },
        {
          round_id: 1,
          partner_id: 77,
          meeting_ids: ["ghi789"],
        },
      ];
      const mockResponse = { success: true, message: "batch deleted" };

      request.post.mockResolvedValue(mockResponse);

      const result = await batchDeleteMeetings(mockDeletions);

      expect(request.post).toHaveBeenCalledWith(
        API_ENDPOINTS.MENTORSHIP_MEETING_V2_BATCH_DELETE,
        {
          deletions: mockDeletions,
        },
      );
      expect(result).toEqual(mockResponse);
    });

    it("should behave normally even when passed an empty deletions array", async () => {
      request.post.mockResolvedValue({ success: true, count: 0 });

      const result = await batchDeleteMeetings([]);

      expect(request.post).toHaveBeenCalledWith(
        API_ENDPOINTS.MENTORSHIP_MEETING_V2_BATCH_DELETE,
        { deletions: [] },
      );
      expect(result.count).toBe(0);
    });
  });

  describe("getMyMentorshipMeetingsV2", () => {
    it("should call GET endpoint with round_id and include_details: false", async () => {
      const mockRoundId = 99;
      const mockIncludeDetails = true;
      const mockResponse = [
        { id: "m1", topic: "First Sync" },
        { id: "m2", topic: "Second Sync" },
      ];

      request.get.mockResolvedValue(mockResponse);

      const result = await getMyMentorshipMeetingsV2({
        roundId: mockRoundId,
        includeDetails: mockIncludeDetails,
      });

      expect(request.get).toHaveBeenCalledWith(
        API_ENDPOINTS.MENTORSHIP_MEETINGS_V2,
        {
          params: {
            round_id: mockRoundId,
            include_details: mockIncludeDetails,
          },
        },
      );
      expect(result).toEqual(mockResponse);
    });

    it("should pass undefined for include_details if not provided", async () => {
      request.get.mockResolvedValue([]);

      await getMyMentorshipMeetingsV2({ roundId: 99 });

      expect(request.get).toHaveBeenCalledWith(
        API_ENDPOINTS.MENTORSHIP_MEETINGS_V2,
        { params: { round_id: 99, include_details: undefined } },
      );
    });

    it("should pass the roundId type as-is (Warning: API does not enforce integer conversion)", async () => {
      request.get.mockResolvedValue([]);

      await getMyMentorshipMeetingsV2({ roundId: "99", includeDetails: false });

      expect(request.get).toHaveBeenCalledWith(
        API_ENDPOINTS.MENTORSHIP_MEETINGS_V2,
        { params: { round_id: "99", include_details: false } },
      );
    });

    it("should propagate network errors upward when fetching meetings fails", async () => {
      await assertErrorPropagation(() =>
        getMyMentorshipMeetingsV2({ roundId: 99 }),
      );
    });
  });

  describe("postMyMentorshipMeetingV2", () => {
    it("should call POST endpoint with the correct payload body", async () => {
      const mockPayload = {
        round_id: 1,
        partner_id: 42,
        topic: "Architecture Review",
        meeting_date: "2026-06-01",
      };
      const mockResponse = { id: "new-meeting-001", ...mockPayload };

      request.post.mockResolvedValue(mockResponse);

      const result = await postMyMentorshipMeetingV2(mockPayload);

      expect(request.post).toHaveBeenCalledWith(
        API_ENDPOINTS.MENTORSHIP_MEETINGS_V2,
        mockPayload,
      );
      expect(result).toEqual(mockResponse);
    });

    it("should pass illegal or redundant fields to backend because API lack whitelist filtering", async () => {
      const dirtyPayload = {
        round_id: 1,
        topic: "Valid Topic",
        hacker_field: "malicious_data",
        is_admin: true,
      };
      request.post.mockResolvedValue({ id: "new-id" });

      await postMyMentorshipMeetingV2(dirtyPayload);

      expect(request.post).toHaveBeenCalledWith(
        API_ENDPOINTS.MENTORSHIP_MEETINGS_V2,
        dirtyPayload,
      );
    });

    it("should propagate network errors upward when creation fails", async () => {
      const mockError = { message: "Bad Request", response: { status: 400 } };
      request.post.mockRejectedValue(mockError);

      await expect(postMyMentorshipMeetingV2({})).rejects.toEqual(mockError);
    });
  });
});
