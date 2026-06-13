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
