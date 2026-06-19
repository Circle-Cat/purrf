import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useUserAdmin } from "@/pages/AdminPermissions/hooks/useUserAdmin";
import * as api from "@/api/adminPermissionsApi";

vi.mock("@/api/adminPermissionsApi");

const userPage = (overrides = {}) => ({
  data: {
    users: [
      {
        userId: 1,
        primaryEmail: "a@x.com",
        firstName: "A",
        lastName: "One",
        isActive: true,
        isSuperAdmin: false,
      },
    ],
    total: 1,
    ...overrides,
  },
});

describe("useUserAdmin", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getUsers.mockResolvedValue(userPage());
  });

  it("fetches the first page on mount with limit 20, offset 0", async () => {
    const { result } = renderHook(() => useUserAdmin());
    await waitFor(() => expect(result.current.users).toHaveLength(1));
    expect(api.getUsers).toHaveBeenCalledWith(
      expect.objectContaining({ search: "", limit: 20, offset: 0 }),
    );
    expect(result.current.total).toBe(1);
  });

  it("refetches with the new search term", async () => {
    const { result } = renderHook(() => useUserAdmin());
    await waitFor(() => expect(api.getUsers).toHaveBeenCalled());
    act(() => result.current.setSearch("jo"));
    await waitFor(() =>
      expect(api.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "jo", limit: 20, offset: 0 }),
      ),
    );
  });

  it("nextPage advances offset by limit", async () => {
    api.getUsers.mockResolvedValue(userPage({ total: 50 }));
    const { result } = renderHook(() => useUserAdmin());
    await waitFor(() => expect(result.current.total).toBe(50));
    act(() => result.current.nextPage());
    await waitFor(() =>
      expect(api.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "", limit: 20, offset: 20 }),
      ),
    );
  });

  it("makeSuperAdmin calls the API for the selected user and refreshes", async () => {
    api.setSuperAdmin.mockResolvedValue({
      data: {
        userId: 1,
        primaryEmail: "a@x.com",
        firstName: "A",
        lastName: "One",
        isActive: true,
        isSuperAdmin: true,
      },
    });
    const { result } = renderHook(() => useUserAdmin());
    await waitFor(() => expect(result.current.users).toHaveLength(1));
    act(() => result.current.selectUser(result.current.users[0]));
    await act(async () => {
      await result.current.makeSuperAdmin();
    });
    expect(api.setSuperAdmin).toHaveBeenCalledWith(1);
    expect(result.current.selectedUser.isSuperAdmin).toBe(true);
  });

  it("revokeSuperAdminFor calls the API for the selected user and refreshes", async () => {
    api.revokeSuperAdmin.mockResolvedValue({
      data: {
        userId: 1,
        primaryEmail: "a@x.com",
        firstName: "A",
        lastName: "One",
        isActive: true,
        isSuperAdmin: false,
      },
    });
    const { result } = renderHook(() => useUserAdmin());
    await waitFor(() => expect(result.current.users).toHaveLength(1));
    act(() => result.current.selectUser(result.current.users[0]));
    await act(async () => {
      await result.current.revokeSuperAdminFor();
    });
    expect(api.revokeSuperAdmin).toHaveBeenCalledWith(1);
    expect(result.current.selectedUser.isSuperAdmin).toBe(false);
  });

  it("setIsSuperAdmin(true) refetches with isSuperAdmin:true and resets offset", async () => {
    api.getUsers.mockResolvedValue(userPage({ total: 50 }));
    const { result } = renderHook(() => useUserAdmin());
    await waitFor(() => expect(result.current.total).toBe(50));
    // advance to page 2 first
    act(() => result.current.nextPage());
    await waitFor(() =>
      expect(api.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 20 }),
      ),
    );
    // now toggle filter — offset should reset to 0
    act(() => result.current.setIsSuperAdmin(true));
    await waitFor(() =>
      expect(api.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({ isSuperAdmin: true, offset: 0 }),
      ),
    );
  });

  it("toggleSort(field) sets sortBy and order:asc on first call", async () => {
    const { result } = renderHook(() => useUserAdmin());
    await waitFor(() => expect(result.current.users).toHaveLength(1));
    act(() => result.current.toggleSort("last_name"));
    await waitFor(() =>
      expect(api.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "last_name", order: "asc" }),
      ),
    );
  });

  it("toggleSort(field) flips to desc on second call for same field", async () => {
    const { result } = renderHook(() => useUserAdmin());
    await waitFor(() => expect(result.current.users).toHaveLength(1));
    act(() => result.current.toggleSort("last_name"));
    await waitFor(() =>
      expect(api.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "last_name", order: "asc" }),
      ),
    );
    act(() => result.current.toggleSort("last_name"));
    await waitFor(() =>
      expect(api.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "last_name", order: "desc" }),
      ),
    );
  });
});
