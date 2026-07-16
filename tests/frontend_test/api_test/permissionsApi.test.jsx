import { describe, it, expect, vi, beforeEach } from "vitest";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";
import { getUserPermissions } from "@/api/permissionsApi";
import request from "@/utils/request";

vi.mock("@/utils/request", () => ({
  default: {
    get: vi.fn(),
  },
}));

describe("permissionsApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getUserPermissions", () => {
    it("should call request.get with the correct URL", async () => {
      await getUserPermissions();

      expect(request.get).toHaveBeenCalledTimes(1);
      expect(request.get).toHaveBeenCalledWith(API_ENDPOINTS.MY_PERMISSIONS);
    });
  });
});
