import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/context/auth";
import { USER_ROLES } from "@/constants/UserRoles";
import { getUserRoles } from "@/api/rolesApi";

vi.mock("@/api/rolesApi", () => ({
  getUserRoles: vi.fn(),
}));

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should initialize with loading true and empty roles", () => {
    getUserRoles.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    expect(result.current.loading).toBe(true);
    expect(result.current.roles).toEqual([]);
  });

  it("should provide admin and cc_internal role when API call is successful", async () => {
    const mockRolesData = [USER_ROLES.ADMIN, USER_ROLES.CC_INTERNAL];
    getUserRoles.mockResolvedValue({data: { roles: mockRolesData } });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.roles).toEqual(mockRolesData);
    expect(result.current.roles).toContain(USER_ROLES.ADMIN);
  });

  it("should provide mentorship role when API call is successful", async () => {
    getUserRoles.mockResolvedValue({data: { roles: [USER_ROLES.MENTORSHIP] } });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.roles).toEqual([USER_ROLES.MENTORSHIP]);
  });

  it("should return empty roles when user has no permissions)", async () => {
    getUserRoles.mockResolvedValue({ roles: [] });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.roles).toEqual([]);
  });

  it("should return empty roles when API fails", async () => {
    getUserRoles.mockRejectedValue(new Error("Network Error"));

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.roles).toEqual([]);
  });
});
