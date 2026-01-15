import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getCookie,
  extractCloudflareUserName,
  performGlobalLogout,
} from "@/utils/auth";

vi.stubEnv("VITE_AUTH0_DOMAIN", "auth.test.com");
vi.stubEnv("VITE_AUTH0_CLIENT_ID", "MOCK_CLIENT_ID");
vi.stubEnv("VITE_CF_ACCESS_TENANT_DOMAIN", "tenant.cloudflareaccess.com");

/**
 * Helper function: Mock JWT generation (URL-safe Base64)
 */
const createMockJwt = (payload) => {
  const header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"; // {"alg":"HS256","typ":"JWT"}
  const signature = "signature";
  const payloadBase64 = btoa(JSON.stringify(payload))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
  return `${header}.${payloadBase64}.${signature}`;
};

/**
 * Helper function: Mock document.cookie
 */
const setMockCookie = (cookieString) => {
  Object.defineProperty(document, "cookie", {
    get: vi.fn().mockReturnValue(cookieString),
    configurable: true,
  });
};

describe("auth utils", () => {
  const originalLocation = window.location;
  const originalCookie = document.cookie;

  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "log").mockImplementation(() => {});

    // Mock localStorage and sessionStorage
    const storageMock = (() => {
      let store = {};
      return {
        getItem: (key) => store[key] || null,
        setItem: (key, value) => {
          store[key] = value.toString();
        },
        clear: vi.fn(() => {
          store = {};
        }),
      };
    })();
    vi.stubGlobal("localStorage", storageMock);
    vi.stubGlobal("sessionStorage", storageMock);

    // Mock window.location
    delete window.location;
    window.location = {
      ...originalLocation,
      href: "",
      origin: "https://example.com",
    };
  });

  afterEach(() => {
    window.location = originalLocation;
    Object.defineProperty(document, "cookie", {
      value: originalCookie,
      configurable: true,
    });
    vi.restoreAllMocks();
  });

  describe("getCookie", () => {
    it("should return the cookie value if it exists", () => {
      setMockCookie("other=123; CF_Authorization=some_jwt_token; key=val");
      expect(getCookie("CF_Authorization")).toBe("some_jwt_token");
    });

    it("should return null if the cookie does not exist", () => {
      setMockCookie("some_other_cookie=value");
      expect(getCookie("CF_Authorization")).toBeNull();
    });

    it("should handle multiple cookies", () => {
      setMockCookie(
        "cookie1=value1; CF_Authorization=token123; cookie3=value3",
      );
      expect(getCookie("CF_Authorization")).toBe("token123");
    });

    it("should handle cookies with leading spaces", () => {
      setMockCookie(" cookie1=value1;  CF_Authorization=token123");
      expect(getCookie("CF_Authorization")).toBe("token123");
    });

    it("should return null for an empty cookie string", () => {
      setMockCookie("");
      expect(getCookie("CF_Authorization")).toBeNull();
    });

    it("should not partially match cookie names", () => {
      setMockCookie("long_CF_Authorization=wrong_token");
      expect(getCookie("CF_Authorization")).toBeNull();
    });
  });

  describe("extractCloudflareUserName", () => {
    it("should extract and format username from the UPN field in the JWT", () => {
      const jwt = createMockJwt({ custom: { upn: "test.user@example.com" } });
      expect(extractCloudflareUserName(jwt)).toBe("test.user");
    });

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
    });
  });

  describe("performGlobalLogout", () => {
    it("Local environment should redirect directly to the homepage", () => {
      window.location.origin = "http://localhost:5173";
      performGlobalLogout();
      expect(localStorage.clear).toHaveBeenCalled();
      expect(window.location.href).toBe("http://localhost:5173/");
    });

    it("Auth0 production environment: full chain redirection (Auth0 -> CF -> Home)", () => {
      window.location.origin = "https://example.com";
      const jwt = createMockJwt({
        custom: { sub: "email|12345" },
        email: "user@test.com",
      });
      setMockCookie(`CF_Authorization=${jwt}`);

      performGlobalLogout();

      const rawUrl = window.location.href;
      expect(rawUrl).toContain("https://auth.test.com/v2/logout");

      const decodedTwice = decodeURIComponent(decodeURIComponent(rawUrl));
      expect(decodedTwice).toContain(
        "tenant.cloudflareaccess.com/cdn-cgi/access/logout",
      );
      expect(decodedTwice).toContain("example.com/cdn-cgi/access/logout");
      expect(decodedTwice).toContain("returnTo=https://example.com/");
    });

    it("LDAP user production environment: direct CF chain", () => {
      window.location.origin = "https://example.com";
      const jwt = createMockJwt({ custom: { upn: "ldap@circlecat.org" } });
      setMockCookie(`CF_Authorization=${jwt}`);

      performGlobalLogout();

      const rawUrl = window.location.href;
      expect(rawUrl).not.toContain("auth.test.com");
      const decodedUrl = decodeURIComponent(rawUrl);
      expect(decodedUrl).toContain(
        "tenant.cloudflareaccess.com/cdn-cgi/access/logout",
      );
      expect(decodedUrl).toContain("https://example.com/cdn-cgi/access/logout");
    });

    it("Feature detection: email matches ClientID recognized as Auth0 user", () => {
      window.location.origin = "https://example.com";
      const jwt = createMockJwt({ email: "MOCK_CLIENT_ID" });
      setMockCookie(`CF_Authorization=${jwt}`);

      performGlobalLogout();
      expect(window.location.href).toContain("auth.test.com/v2/logout");
    });
  });
});
