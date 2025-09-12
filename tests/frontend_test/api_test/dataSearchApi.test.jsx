import { describe, it, expect, vi, beforeEach } from "vitest";
import { getJiraIssueBrief, getJiraIssueDetails } from "@/api/dataSearchApi";
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
});
