import { vi, describe, it, expect, beforeEach } from "vitest";
import request from "@/utils/request";
import { deleteMeeting, batchDeleteMeetings } from "@/api/meetingApi";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

vi.mock("@/utils/request", () => {
  return {
    default: {
      post: vi.fn(),
      delete: vi.fn(),
    },
  };
});

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
      const mockAxiosError = {
        message: "Network Error",
        response: { status: 500, data: "Internal Server Error" },
      };
      request.delete.mockRejectedValue(mockAxiosError);

      await expect(deleteMeeting("abc123", 1, 42)).rejects.toEqual(
        mockAxiosError,
      );
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
});
