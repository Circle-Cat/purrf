import { describe, it, expect, vi, beforeEach } from "vitest";
import { getSummary } from "@/api/dashboardApi";
import request from "@/utils/request";
import { getMySummary } from "@/api/dashboardApi";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

const mockSummaryData = { summary: "This is a summary" };

vi.mock("@/utils/request", () => ({
  default: {
    post: vi.fn(),
  },
}));

describe("dashboardApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getSummary", () => {
    it("should call request.post with the correct URL and body from an object", async () => {
      const params = {
        startDate: "2024-01-01",
        endDate: "2024-01-31",
        includeTerminated: false,
        groups: ["Interns", "Employees"],
      };

      request.post.mockResolvedValue(mockSummaryData);

      await getSummary(params);

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith("/summary", {
        startDate: params.startDate,
        endDate: params.endDate,
        includeTerminated: params.includeTerminated,
        groups: params.groups,
      });
    });

    it("should return the data from the response on success", async () => {
      const params = {
        startDate: "2024-01-01",
        endDate: "2024-01-31",
        includeTerminated: true,
        groups: ["Volunteers"],
      };

      request.post.mockResolvedValue(mockSummaryData);

      const result = await getSummary(params);

      expect(result).toEqual(mockSummaryData);
    });

    it("should throw an error if the request fails", async () => {
      const errorMessage = "Network Error";
      const params = {
        startDate: "2024-01-01",
        endDate: "2024-01-31",
        includeTerminated: true,
        groups: ["Volunteers"],
      };

      request.post.mockRejectedValue(new Error(errorMessage));

      await expect(getSummary(params)).rejects.toThrow(errorMessage);
    });
  });

  describe("getMySummary", () => {
    it("should call request.post with correct endpoint and params", async () => {
      const params = {
        startDate: "2024-01-01",
        endDate: "2024-01-31",
      };

      const mockResponse = { data: { success: true } };

      request.post.mockResolvedValue(mockResponse);

      await getMySummary(params);

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith(
        API_ENDPOINTS.MY_INTERNAL_ACTIVITY_SUMMARY,
        {
          startDate: params.startDate,
          endDate: params.endDate,
        },
      );
    });

    it("should return response data on success", async () => {
      const params = {
        startDate: "2024-01-01",
        endDate: "2024-01-31",
      };

      const mockResponse = { data: { success: true } };

      request.post.mockResolvedValue(mockResponse);

      const result = await getMySummary(params);

      expect(result).toEqual(mockResponse);
    });

    it("should throw error when request fails", async () => {
      const params = {
        startDate: "2024-01-01",
        endDate: "2024-01-31",
      };

      const error = new Error("Request failed");

      request.post.mockRejectedValue(error);

      await expect(getMySummary(params)).rejects.toThrow("Request failed");
    });
  });
});
