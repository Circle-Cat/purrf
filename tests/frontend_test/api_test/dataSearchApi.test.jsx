import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getJiraIssueBrief,
  getJiraIssueDetails,
  getGoogleCalendarEvents,
  getGoogleChatMessagesCount,
  getMicrosoftChatMessagesCount,
} from "@/api/dataSearchApi";
import request from "@/utils/request";

vi.mock("@/utils/request", () => ({
  default: {
    post: vi.fn(),
  },
}));

describe("dataSearchApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getJiraIssueBrief", () => {
    it("should call request.post with the correct URL and body", async () => {
      const params = {
        startDate: "2024-01-01",
        endDate: "2024-01-31",
        projectIds: ["PROJ1"],
        statusList: ["Done"],
        ldaps: ["user1"],
      };
      const mockResponse = { data: { success: true } };
      request.post.mockResolvedValue(mockResponse);

      await getJiraIssueBrief(params);

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith("/jira/brief", params);
    });

    it("should return the data from the response on success", async () => {
      const params = { ldaps: ["user1"] };
      const mockResponse = { data: { user1: { done: [] } } };
      request.post.mockResolvedValue(mockResponse);

      const result = await getJiraIssueBrief(params);

      expect(result).toEqual(mockResponse);
    });

    it("should throw an error if the request fails", async () => {
      const params = { ldaps: ["user1"] };
      const errorMessage = "Network Error";
      request.post.mockRejectedValue(new Error(errorMessage));

      await expect(getJiraIssueBrief(params)).rejects.toThrow(errorMessage);
    });
  });

  describe("getJiraIssueDetails", () => {
    it("should call request.post with the correct URL and body", async () => {
      const params = { issueIds: ["JIRA-1", "JIRA-2"] };
      const mockResponse = { data: { "JIRA-1": {} } };
      request.post.mockResolvedValue(mockResponse);

      await getJiraIssueDetails(params);

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith("/jira/detail/batch", params);
    });

    it("should throw an error if the request fails", async () => {
      const params = { issueIds: ["JIRA-1"] };
      const errorMessage = "API failure";
      request.post.mockRejectedValue(new Error(errorMessage));

      await expect(getJiraIssueDetails(params)).rejects.toThrow(errorMessage);
    });
  });

  describe("getGoogleCalendarEvents", () => {
    it("should call request.post with the correct URL and body", async () => {
      const params = {
        startDate: "2024-03-01",
        endDate: "2024-03-31",
        calendarIds: ["calendar1", "calendar2"],
        ldaps: ["userA", "userB"],
      };
      const mockResponse = { data: { events: [] } };
      request.post.mockResolvedValue(mockResponse);

      await getGoogleCalendarEvents(params);

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith("/calendar/events", params);
    });

    it("should return the data from the response on success", async () => {
      const params = {
        startDate: "2024-03-01",
        endDate: "2024-03-01",
        calendarIds: ["test_calendar"],
        ldaps: ["test_user"],
      };
      const mockEvents = [
        { id: "event1", summary: "Meeting" },
        { id: "event2", summary: "Appointment" },
      ];
      const mockResponse = { data: { events: mockEvents } };
      request.post.mockResolvedValue(mockResponse);

      const result = await getGoogleCalendarEvents(params);

      expect(result).toEqual(mockResponse);
    });

    it("should throw an error if the request fails", async () => {
      const params = {
        startDate: "2024-03-01",
        endDate: "2024-03-01",
        calendarIds: ["calendar_error"],
        ldaps: ["error_user"],
      };
      const errorMessage = "Failed to fetch calendar events";
      request.post.mockRejectedValue(new Error(errorMessage));

      await expect(getGoogleCalendarEvents(params)).rejects.toThrow(
        errorMessage,
      );
    });
  });
  describe("getGoogleChatMessagesCount", () => {
    const mockGoogleParams = {
      startDate: "2024-05-01",
      endDate: "2024-05-07",
      spaceIds: ["SPACE123", "SPACE456"],
      ldaps: ["user1", "user2"],
    };

    it("should call request.post with the correct URL and body", async () => {
      const mockResponse = { data: { success: true, result: {} } };
      request.post.mockResolvedValue(mockResponse);

      await getGoogleChatMessagesCount(mockGoogleParams);

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith(
        "/google/chat/count",
        mockGoogleParams,
      );
    });

    it("should return the data from the response on success", async () => {
      const mockSuccessResponse = {
        data: {
          result: {
            user1: { SPACE123: 10, SPACE456: 5 },
            user2: { SPACE123: 0, SPACE456: 20 },
          },
        },
      };
      request.post.mockResolvedValue(mockSuccessResponse);

      const result = await getGoogleChatMessagesCount(mockGoogleParams);

      expect(result).toEqual(mockSuccessResponse);
    });

    it("should throw an error if the request fails", async () => {
      const errorMessage = "Google Chat API Error";

      request.post.mockRejectedValue(new Error(errorMessage));

      await expect(
        getGoogleChatMessagesCount(mockGoogleParams),
      ).rejects.toThrow(errorMessage);
    });
  });

  describe("getMicrosoftChatMessagesCount", () => {
    const mockMicrosoftParams = {
      ldaps: ["userA", "userB"],
      startDate: "2024-06-01",
      endDate: "2024-06-30",
    };

    it("should call request.post with the correct URL and body", async () => {
      const mockResponse = { data: { success: true, result: {} } };
      request.post.mockResolvedValue(mockResponse);

      await getMicrosoftChatMessagesCount(mockMicrosoftParams);

      expect(request.post).toHaveBeenCalledTimes(1);

      expect(request.post).toHaveBeenCalledWith(
        "/microsoft/chat/count",
        mockMicrosoftParams,
      );
    });

    it("should return the data from the response on success", async () => {
      const mockSuccessResponse = {
        data: {
          result: {
            userA: 50,
            userB: 75,
          },
        },
      };
      request.post.mockResolvedValue(mockSuccessResponse);

      const result = await getMicrosoftChatMessagesCount(mockMicrosoftParams);

      expect(result).toEqual(mockSuccessResponse);
    });

    it("should throw an error if the request fails", async () => {
      const errorMessage = "Microsoft Chat API Failure";
      request.post.mockRejectedValue(new Error(errorMessage));

      await expect(
        getMicrosoftChatMessagesCount(mockMicrosoftParams),
      ).rejects.toThrow(errorMessage);
    });
  });
});
