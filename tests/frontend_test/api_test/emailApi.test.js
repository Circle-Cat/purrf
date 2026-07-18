import { describe, it, expect, vi, beforeEach } from "vitest";

import {
  initiateEmailVerification,
  verifyEmailOtp,
  listEmails,
  initiateSetPrimary,
  confirmSetPrimary,
  initiateUnlink,
  confirmUnlink,
} from "@/api/emailApi";
import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

vi.mock("@/utils/request", () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
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
        data: { ok: true, email: "alice@gmail.com" },
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

  describe("listEmails", () => {
    it("gets the email list endpoint and returns the response", async () => {
      const response = {
        data: {
          emails: [
            {
              emailId: 1,
              email: "alice@gmail.com",
              otpConfirmed: true,
              isPrimary: true,
              addedAt: "2026-01-01T00:00:00Z",
              linkedIdentityCount: 1,
            },
          ],
          internalIdentities: [],
          externalIdentities: [],
        },
      };
      request.get.mockResolvedValue(response);

      const result = await listEmails();

      expect(request.get).toHaveBeenCalledTimes(1);
      expect(request.get).toHaveBeenCalledWith(API_ENDPOINTS.EMAIL_LIST);
      expect(result).toBe(response);
    });

    it("propagates errors from the request layer", async () => {
      const error = new Error("network down");
      request.get.mockRejectedValue(error);

      await expect(listEmails()).rejects.toThrow("network down");
    });
  });

  describe("initiateSetPrimary", () => {
    it("posts to the per-email set-primary initiate endpoint", async () => {
      const response = { data: { state: "signed.jwt" } };
      request.post.mockResolvedValue(response);

      const result = await initiateSetPrimary(42);

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith(
        API_ENDPOINTS.EMAIL_SET_PRIMARY_INITIATE(42),
      );
      expect(request.post).toHaveBeenCalledWith(
        "/auth/emails/42/primary/initiate",
      );
      expect(result).toBe(response);
    });
  });

  describe("confirmSetPrimary", () => {
    it("posts the state and code to the per-email set-primary confirm endpoint", async () => {
      const response = { data: { ok: true } };
      request.post.mockResolvedValue(response);

      const result = await confirmSetPrimary(42, "signed.jwt", "123456");

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith(
        API_ENDPOINTS.EMAIL_SET_PRIMARY_CONFIRM(42),
        { state: "signed.jwt", code: "123456" },
      );
      expect(request.post).toHaveBeenCalledWith(
        "/auth/emails/42/primary/confirm",
        { state: "signed.jwt", code: "123456" },
      );
      expect(result).toBe(response);
    });
  });

  describe("initiateUnlink", () => {
    it("posts to the per-identity unlink initiate endpoint", async () => {
      const response = { data: { state: "signed.jwt" } };
      request.post.mockResolvedValue(response);

      const result = await initiateUnlink(7);

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith(
        API_ENDPOINTS.EMAIL_UNLINK_INITIATE(7),
      );
      expect(request.post).toHaveBeenCalledWith(
        "/auth/identities/7/unlink/initiate",
      );
      expect(result).toBe(response);
    });
  });

  describe("confirmUnlink", () => {
    it("posts the state and code to the per-identity unlink confirm endpoint", async () => {
      const response = { data: { ok: true } };
      request.post.mockResolvedValue(response);

      const result = await confirmUnlink(7, "signed.jwt", "654321");

      expect(request.post).toHaveBeenCalledTimes(1);
      expect(request.post).toHaveBeenCalledWith(
        API_ENDPOINTS.EMAIL_UNLINK_CONFIRM(7),
        { state: "signed.jwt", code: "654321" },
      );
      expect(request.post).toHaveBeenCalledWith(
        "/auth/identities/7/unlink/confirm",
        { state: "signed.jwt", code: "654321" },
      );
      expect(result).toBe(response);
    });
  });
});
