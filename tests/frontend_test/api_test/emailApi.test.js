import { describe, it, expect, vi, beforeEach } from "vitest";

import { initiateEmailVerification, verifyEmailOtp } from "@/api/emailApi";
import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

vi.mock("@/utils/request", () => ({
  default: {
    post: vi.fn(),
  },
}));

describe("emailApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("initiateEmailVerification", () => {
    it("posts the email to the initiate endpoint and returns the response", async () => {
      const response = { data: { state: "signed.jwt" } };
      request.post.mockResolvedValue(response);

      const result = await initiateEmailVerification("alice@gmail.com");

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith(
        API_ENDPOINTS.EMAIL_OTP_INITIATE,
        {
          email: "alice@gmail.com",
        },
      );
      expect(result).toBe(response);
    });
  });

  describe("verifyEmailOtp", () => {
    it("posts the state and otp to the verify endpoint and returns the response", async () => {
      const response = {
        data: { ok: true, linked_sub: "email|abc", email: "alice@gmail.com" },
      };
      request.post.mockResolvedValue(response);

      const result = await verifyEmailOtp("signed.jwt", "123456");

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith(
        API_ENDPOINTS.EMAIL_OTP_VERIFY,
        {
          state: "signed.jwt",
          otp: "123456",
        },
      );
      expect(result).toBe(response);
    });
  });
});
