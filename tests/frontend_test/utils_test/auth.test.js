import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getCookie, extractCloudflareUserName } from "@/utils/auth";

describe("auth utils", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "log").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("getCookie", () => {
    // Mock document.cookie
    const defineCookie = (value) => {
      Object.defineProperty(document, "cookie", {
        get: vi.fn().mockReturnValue(value),
        configurable: true,
      });
    };

    it("should return the cookie value if it exists", () => {
      defineCookie("CF_Authorization=some_jwt_token");
      expect(getCookie("CF_Authorization")).toBe("some_jwt_token");
    });

    it("should return null if the cookie does not exist", () => {
      defineCookie("some_other_cookie=value");
      expect(getCookie("CF_Authorization")).toBeNull();
    });

    it("should handle multiple cookies", () => {
      defineCookie("cookie1=value1; CF_Authorization=token123; cookie3=value3");
      expect(getCookie("CF_Authorization")).toBe("token123");
    });

    it("should handle cookies with leading spaces", () => {
      defineCookie(" cookie1=value1;  CF_Authorization=token123");
      expect(getCookie("CF_Authorization")).toBe("token123");
    });

    it("should return null for an empty cookie string", () => {
      defineCookie("");
      expect(getCookie("CF_Authorization")).toBeNull();
    });

    it("should not partially match cookie names", () => {
      defineCookie("long_CF_Authorization=wrong_token");
      expect(getCookie("CF_Authorization")).toBeNull();
    });
  });

  describe("extractCloudflareUserName", () => {
    /**
     * Creates a mock JWT string for testing purposes.
     *
     * The JWT is constructed as follows:
     * 1. The header is fixed: {"alg":"HS256","typ":"JWT"} (base64-encoded).
     * 2. The payload is JSON-stringified, then base64-encoded and made URL-safe:
     *    + → -, / → _, = → ''.
     * 3. The signature is a fixed placeholder string "signature".
     *
     * @param {Object} payload - The payload object to include in the JWT.
     * @returns {string} A mock JWT string in the format header.payload.signature.
     *
     * @example
     * const jwt = createMockJwt({ user: "Alice" });
     * console.log(jwt); // eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<encoded payload>.signature
     */
    const createMockJwt = (payload) => {
      const header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9";
      const signature = "signature";
      const payloadBase64 = btoa(JSON.stringify(payload))
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=/g, "");
      return `${header}.${payloadBase64}.${signature}`;
    };

    it("should return null if jwtString is null or undefined", () => {
      expect(extractCloudflareUserName(null)).toBeNull();
      expect(extractCloudflareUserName(undefined)).toBeNull();
    });

    it("should return null for an invalid JWT format", () => {
      expect(extractCloudflareUserName("invalid.jwt")).toBeNull();
      expect(console.warn).toHaveBeenCalledWith(
        "JWT format is incorrect, not a valid JWT.",
      );
    });

    it("should extract username from custom.upn (Azure)", () => {
      const jwt = createMockJwt({ custom: { upn: "azureuser@domain.com" } });
      expect(extractCloudflareUserName(jwt)).toBe("azureuser");
    });

    it("should extract username from custom.email (Google)", () => {
      const jwt = createMockJwt({ custom: { email: "googleuser@domain.com" } });
      expect(extractCloudflareUserName(jwt)).toBe("googleuser");
    });

    it("should extract username from email (One-time PIN)", () => {
      const jwt = createMockJwt({ email: "pinuser@domain.com" });
      expect(extractCloudflareUserName(jwt)).toBe("pinuser");
    });

    it("should prioritize custom.upn over other fields", () => {
      const jwt = createMockJwt({
        custom: { upn: "azureuser@domain.com", email: "googleuser@domain.com" },
        email: "pinuser@domain.com",
      });
      expect(extractCloudflareUserName(jwt)).toBe("azureuser");
    });

    it("should prioritize custom.email over email field", () => {
      const jwt = createMockJwt({
        custom: { email: "googleuser@domain.com" },
        email: "pinuser@domain.com",
      });
      expect(extractCloudflareUserName(jwt)).toBe("googleuser");
    });

    it("should return the full name if it's not an email", () => {
      const jwt = createMockJwt({ custom: { upn: "plainusername" } });
      expect(extractCloudflareUserName(jwt)).toBe("plainusername");
    });

    it("should return null if no user identifier is found", () => {
      const jwt = createMockJwt({ other: "data" });
      expect(extractCloudflareUserName(jwt)).toBeNull();
    });

    /**
     * Test case: returns null if the JWT payload is not valid JSON.
     *
     * The JWT is constructed as follows:
     * 1. The header is fixed: {"alg":"HS256","typ":"JWT"} (base64-encoded).
     * 2. An invalid base64 payload that does not decode to JSON.
     * 3. The signature is a fixed placeholder string "signature".
     */
    it("should return null if payload is not valid JSON", () => {
      const header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9";
      const invalidPayload = "bm90LWEtanNvbg"; // "not-a-json"
      const signature = "signature";
      const jwt = `${header}.${invalidPayload}.${signature}`;
      expect(extractCloudflareUserName(jwt)).toBeNull();
      expect(console.error).toHaveBeenCalledWith(
        "Failed to parse or extract username from Cloudflare JWT:",
        expect.any(Error),
      );
    });
  });
});
