import { describe, it, expect, vi, beforeEach } from "vitest";
import { getSummary } from "@/api/dashboardApi";
import request from "@/utils/request";

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
});
