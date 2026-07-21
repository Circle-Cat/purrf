import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import { getUserPermissions } from "@/api/permissionsApi";

vi.mock("@/api/permissionsApi", () => ({
  getUserPermissions: vi.fn(),
}));

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should initialize with loading true and empty permissions", () => {
    getUserPermissions.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    expect(result.current.loading).toBe(true);
    expect(result.current.permissions).toEqual([]);
  });

  it("should provide permissions when API call is successful", async () => {
    const mockPermissions = [
      PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ,
      PERMISSIONS.INTERNAL_ACTIVITY_READ,
    ];
    getUserPermissions.mockResolvedValue({
      data: { permissions: mockPermissions, is_super_admin: false },
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.permissions).toEqual(mockPermissions);
    expect(result.current.permissions).toContain(
      PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ,
    );
  });

  it("should expose identity and super-admin flag from the API", async () => {
    getUserPermissions.mockResolvedValue({
      data: {
        permissions: [],
        sub: "u1",
        user_id: 7,
        email: "a@b.com",
        identity_type: "internal",
        is_super_admin: true,
      },
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isSuperAdmin).toBe(true);
    expect(result.current.user).toEqual({
      sub: "u1",
      userId: 7,
      email: "a@b.com",
      identityType: "internal",
    });
  });

  it("should return empty permissions when user has none", async () => {
    getUserPermissions.mockResolvedValue({ data: { permissions: [] } });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.permissions).toEqual([]);
  });

  it("should return empty permissions when API fails", async () => {
    getUserPermissions.mockRejectedValue(new Error("Network Error"));

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.permissions).toEqual([]);
    expect(result.current.accessDenied).toBe(false);
  });

  it("flags a transient load failure as authError without sessionExpired", async () => {
    getUserPermissions.mockRejectedValue(new Error("Network Error"));

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    // A network/timeout/5xx failure must NOT masquerade as an unverified user.
    expect(result.current.authError).toBe(true);
    expect(result.current.sessionExpired).toBe(false);
    expect(result.current.accessDenied).toBe(false);
  });

  it("flags a 401 as a session expiry, not a verify-wall case", async () => {
    getUserPermissions.mockRejectedValue({ response: { status: 401 } });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.authError).toBe(true);
    expect(result.current.sessionExpired).toBe(true);
    expect(result.current.accessDenied).toBe(false);
  });

  it("does not set authError on a 403 (that path is accessDenied)", async () => {
    getUserPermissions.mockRejectedValue({ response: { status: 403 } });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.accessDenied).toBe(true);
    expect(result.current.authError).toBe(false);
  });

  it("clears authError once a retry succeeds", async () => {
    getUserPermissions
      .mockRejectedValueOnce({ response: { status: 401 } })
      .mockResolvedValueOnce({
        data: { permissions: [], has_verified_email: true },
      });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.authError).toBe(true);

    await act(async () => {
      await result.current.refreshAuth();
    });

    expect(result.current.authError).toBe(false);
    expect(result.current.sessionExpired).toBe(false);
    expect(result.current.hasVerifiedEmail).toBe(true);
  });

  it("flags accessDenied with the message on a 403 (e.g. deactivated account)", async () => {
    const message =
      "Your account has been deactivated. Contact an administrator to restore access.";
    getUserPermissions.mockRejectedValue({
      response: { status: 403, data: { message } },
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.accessDenied).toBe(true);
    expect(result.current.accessDeniedMessage).toBe(message);
    expect(result.current.hasVerifiedEmail).toBe(false);
  });

  it("flags accessDenied with an empty message when the 403 has no body", async () => {
    getUserPermissions.mockRejectedValue({
      response: { status: 403 },
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.accessDenied).toBe(true);
    expect(result.current.accessDeniedMessage).toBe("");
  });

  it("captures the server's refusal message on a 400 with a message", async () => {
    const message = "Sign in with a supported method.";
    getUserPermissions.mockRejectedValue({
      response: { status: 400, data: { message } },
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.authError).toBe(true);
    expect(result.current.authRefusalMessage).toBe(message);
    expect(result.current.accessDenied).toBe(false);
    expect(result.current.sessionExpired).toBe(false);
  });

  it("leaves authRefusalMessage null on a 400 without a message", async () => {
    getUserPermissions.mockRejectedValue({
      response: { status: 400 },
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.authError).toBe(true);
    expect(result.current.authRefusalMessage).toBe(null);
  });

  it("leaves authRefusalMessage null on a network error", async () => {
    getUserPermissions.mockRejectedValue(new Error("Network Error"));

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.authRefusalMessage).toBe(null);
  });

  it("leaves authRefusalMessage null on a 5xx", async () => {
    getUserPermissions.mockRejectedValue({
      response: { status: 500, data: { message: "boom" } },
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.authRefusalMessage).toBe(null);
  });

  it("leaves authRefusalMessage null on a 401", async () => {
    getUserPermissions.mockRejectedValue({
      response: { status: 401, data: { message: "expired" } },
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.authRefusalMessage).toBe(null);
  });

  it("leaves authRefusalMessage null on a 403", async () => {
    getUserPermissions.mockRejectedValue({
      response: { status: 403, data: { message: "deactivated" } },
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.authRefusalMessage).toBe(null);
  });

  it("clears a captured refusal message once a retry succeeds", async () => {
    const message = "Sign in with a supported method.";
    getUserPermissions
      .mockRejectedValueOnce({ response: { status: 400, data: { message } } })
      .mockResolvedValueOnce({ data: { permissions: [] } });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.authRefusalMessage).toBe(message);

    await act(async () => {
      await result.current.refreshAuth();
    });

    expect(result.current.authRefusalMessage).toBe(null);
    expect(result.current.authError).toBe(false);
  });

  it("exposes hasVerifiedEmail true when the API reports a verified email", async () => {
    getUserPermissions.mockResolvedValue({
      data: { permissions: [], has_verified_email: true },
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.hasVerifiedEmail).toBe(true);
  });

  it("defaults hasVerifiedEmail to false when the flag is absent", async () => {
    getUserPermissions.mockResolvedValue({ data: { permissions: [] } });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.hasVerifiedEmail).toBe(false);
  });

  it("refreshAuth re-pulls auth state so a freshly verified email is reflected", async () => {
    getUserPermissions
      .mockResolvedValueOnce({
        data: { permissions: [], has_verified_email: false },
      })
      .mockResolvedValueOnce({
        data: { permissions: [], has_verified_email: true },
      });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.hasVerifiedEmail).toBe(false);

    await act(async () => {
      await result.current.refreshAuth();
    });

    expect(result.current.hasVerifiedEmail).toBe(true);
    expect(getUserPermissions).toHaveBeenCalledTimes(2);
  });
});
