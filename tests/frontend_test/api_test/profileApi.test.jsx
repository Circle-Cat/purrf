import { describe, it, expect, vi, beforeEach } from "vitest";
import { updateMyProfile } from "@/api/profileApi";
import { getMyProfile } from "@/api/profileApi";
import request from "@/utils/request";

vi.mock("@/utils/request", () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
  },
}));

describe("profileApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getMyProfile", () => {
    it("should call request.get with the correct URL when no fields are provided", async () => {
      await getMyProfile();

      expect(request.get).toHaveBeenCalledTimes(1);
      expect(request.get).toHaveBeenCalledWith("/profiles/me");
    });

    it("should call request.get with the correct URL and fields is Array", async () => {
      const params = { fields: ["user", "experience"] };
      await getMyProfile(params);

      expect(request.get).toHaveBeenCalledTimes(1);
      expect(request.get).toHaveBeenCalledWith(
        "/profiles/me?fields=user%2Cexperience",
      );
    });

    it("should call request.get with the correct URL when fields is a string", async () => {
      const params = { fields: "user,experience" };
      await getMyProfile(params);

      expect(request.get).toHaveBeenCalledTimes(1);
      expect(request.get).toHaveBeenCalledWith("/profiles/me");
    });
  });

  describe("updateMyProfile", () => {
    it("should call request.patch with the correct URL and profile Object", async () => {
      await updateMyProfile({ profile: {} });

      expect(request.patch).toHaveBeenCalledTimes(1);
      expect(request.patch).toHaveBeenCalledWith(
        "/profiles/me",
        expect.objectContaining({
          profile: expect.any(Object),
        }),
      );
    });
  });
});
