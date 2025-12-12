import { describe, it, expect, vi, beforeEach } from "vitest";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";
import { getUserRoles } from "@/api/rolesApi";
import request from "@/utils/request";

vi.mock("@/utils/request", () => ({
  default: {
    get: vi.fn(),
  },
}));

describe("rolesApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getUserRoles", () => {
    it("should call request.get with the correct URL", async () => {
      await getUserRoles();

      expect(request.get).toHaveBeenCalledTimes(1);
      expect(request.get).toHaveBeenCalledWith(API_ENDPOINTS.MY_ROLES);
    });
  });
});
