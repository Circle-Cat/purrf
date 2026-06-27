import { describe, it, expect } from "vitest";

import {
  EMAIL_PROVIDER,
  PROVIDER_LABELS,
  providerOf,
  providerLabel,
  isEmailMethod,
  identityLabel,
} from "@/pages/SignInSecurity/providers";

describe("SignInSecurity providers", () => {
  describe("providerOf", () => {
    it("returns the provider prefix of a provider|id subject", () => {
      expect(providerOf("google-oauth2|123")).toBe("google-oauth2");
      expect(providerOf("email|abc")).toBe("email");
    });

    it("returns an empty string for a nullish subject", () => {
      expect(providerOf(undefined)).toBe("");
      expect(providerOf("")).toBe("");
    });
  });

  describe("providerLabel", () => {
    it("maps known providers to their human label", () => {
      expect(providerLabel("google-oauth2|1")).toBe("Google");
      expect(providerLabel("google|1")).toBe("Google");
      expect(providerLabel(`${EMAIL_PROVIDER}|1`)).toBe("Email");
      expect(providerLabel("auth0|1")).toBe("Email & password");
    });

    it("echoes an unknown provider prefix", () => {
      expect(providerLabel("github|1")).toBe("github");
    });

    it("falls back to Unknown when there is no provider", () => {
      expect(providerLabel("")).toBe("Unknown");
      expect(providerLabel(undefined)).toBe("Unknown");
    });
  });

  describe("isEmailMethod", () => {
    it("is true only for the email-OTP provider", () => {
      expect(isEmailMethod(`${EMAIL_PROVIDER}|1`)).toBe(true);
    });

    it("is false for SSO and email-and-password providers", () => {
      expect(isEmailMethod("google-oauth2|1")).toBe(false);
      expect(isEmailMethod("auth0|1")).toBe(false);
      expect(isEmailMethod(undefined)).toBe(false);
    });
  });

  describe("identityLabel", () => {
    it("suffixes the provider label with the email claim when present", () => {
      expect(
        identityLabel({
          subjectIdentifier: "google-oauth2|1",
          emailClaim: "alice@gmail.com",
        }),
      ).toBe("Google (alice@gmail.com)");
    });

    it("uses just the provider label when there is no email claim", () => {
      expect(identityLabel({ subjectIdentifier: "auth0|1" })).toBe(
        "Email & password",
      );
    });

    it("falls back to a generic phrase for an unknown, claimless provider", () => {
      expect(identityLabel({ subjectIdentifier: "" })).toBe(
        "this sign-in method",
      );
    });
  });

  it("labels every mapped provider", () => {
    expect(PROVIDER_LABELS[EMAIL_PROVIDER]).toBe("Email");
  });
});
