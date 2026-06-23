import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { usePermissionHolders } from "@/pages/AdminPermissions/hooks/usePermissionHolders";
import * as api from "@/api/adminPermissionsApi";

vi.mock("@/api/adminPermissionsApi");

beforeEach(() => {
  vi.clearAllMocks();
  api.getPermissionHolders.mockResolvedValue({ data: { grants: [{ id: 1 }] } });
});

describe("usePermissionHolders", () => {
  it("does not fetch on mount or when only a permission is chosen", async () => {
    const { result } = renderHook(() => usePermissionHolders());
    await act(async () => {});
    expect(api.getPermissionHolders).not.toHaveBeenCalled();
    act(() => result.current.setPermissionName("permission.manage"));
    await act(async () => {});
    expect(api.getPermissionHolders).not.toHaveBeenCalled();
    expect(result.current.hasSearched).toBe(false);
  });

  it("fetches with the committed permission + filters on submitSearch", async () => {
    const { result } = renderHook(() => usePermissionHolders());
    act(() => result.current.setPermissionName("permission.manage"));
    act(() => result.current.submitSearch());
    await waitFor(() =>
      expect(api.getPermissionHolders).toHaveBeenCalledWith(
        "permission.manage",
        { includeRevoked: false },
      ),
    );
    await waitFor(() => expect(result.current.grants).toEqual([{ id: 1 }]));
    expect(result.current.hasSearched).toBe(true);
  });

  it("does not re-fetch when includeRevoked toggles until submitSearch", async () => {
    const { result } = renderHook(() => usePermissionHolders());
    act(() => result.current.setPermissionName("permission.manage"));
    act(() => result.current.submitSearch());
    await waitFor(() =>
      expect(api.getPermissionHolders).toHaveBeenCalledTimes(1),
    );
    act(() => result.current.setIncludeRevoked(true));
    await act(async () => {});
    expect(api.getPermissionHolders).toHaveBeenCalledTimes(1);
    act(() => result.current.submitSearch());
    await waitFor(() =>
      expect(api.getPermissionHolders).toHaveBeenLastCalledWith(
        "permission.manage",
        { includeRevoked: true },
      ),
    );
  });
});
