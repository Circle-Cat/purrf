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
  it("does not fetch until a permission is chosen", async () => {
    renderHook(() => usePermissionHolders());
    await act(async () => {});
    expect(api.getPermissionHolders).not.toHaveBeenCalled();
  });

  it("fetches with filters when a permission is chosen", async () => {
    const { result } = renderHook(() => usePermissionHolders());
    act(() => result.current.setPermissionName("permission.manage"));
    await waitFor(() =>
      expect(api.getPermissionHolders).toHaveBeenCalledWith(
        "permission.manage",
        {
          includeRevoked: false,
        },
      ),
    );
    await waitFor(() => expect(result.current.grants).toEqual([{ id: 1 }]));
  });

  it("re-fetches when includeRevoked toggles", async () => {
    const { result } = renderHook(() => usePermissionHolders());
    act(() => result.current.setPermissionName("permission.manage"));
    await waitFor(() =>
      expect(api.getPermissionHolders).toHaveBeenCalledTimes(1),
    );
    act(() => result.current.setIncludeRevoked(true));
    await waitFor(() =>
      expect(api.getPermissionHolders).toHaveBeenLastCalledWith(
        "permission.manage",
        {
          includeRevoked: true,
        },
      ),
    );
  });
});
