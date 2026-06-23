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

  it("does not fetch on mount and reports hasSearched=false", async () => {
    const { result } = renderHook(() => useUserAdmin());
    await act(async () => {});
    expect(api.getUsers).not.toHaveBeenCalled();
    expect(result.current.hasSearched).toBe(false);
  });

  it("does not fetch on a draft input change until submitSearch", async () => {
    const { result } = renderHook(() => useUserAdmin());
    act(() => result.current.setSearch("jo"));
    await act(async () => {});
    expect(api.getUsers).not.toHaveBeenCalled();
  });

  it("submitSearch fetches with the committed search term, limit 20, offset 0", async () => {
    const { result } = renderHook(() => useUserAdmin());
    act(() => result.current.setSearch("jo"));
    act(() => result.current.submitSearch());
    await waitFor(() => expect(result.current.total).toBe(1));
    expect(api.getUsers).toHaveBeenCalledWith(
      expect.objectContaining({ search: "jo", limit: 20, offset: 0 }),
    );
    expect(result.current.hasSearched).toBe(true);
  });

  it("submitSearch sends the userId param for exact-match search", async () => {
    const { result } = renderHook(() => useUserAdmin());
    act(() => result.current.setUserId("42"));
    act(() => result.current.submitSearch());
    await waitFor(() =>
      expect(api.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({ userId: "42" }),
      ),
    );
  });

  it("nextPage advances offset by limit after a search", async () => {
    api.getUsers.mockResolvedValue(userPage({ total: 50 }));
    const { result } = renderHook(() => useUserAdmin());
    act(() => result.current.submitSearch());
    await waitFor(() => expect(result.current.total).toBe(50));
    act(() => result.current.nextPage());
    await waitFor(() =>
      expect(api.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({ limit: 20, offset: 20 }),
      ),
    );
  });

  it("filters are draft: setIsSuperAdmin does not refetch until submitSearch", async () => {
    const { result } = renderHook(() => useUserAdmin());
    act(() => result.current.submitSearch());
    await waitFor(() => expect(api.getUsers).toHaveBeenCalledTimes(1));
    act(() => result.current.setIsSuperAdmin(true));
    await act(async () => {});
    expect(api.getUsers).toHaveBeenCalledTimes(1);
    act(() => result.current.submitSearch());
    await waitFor(() =>
      expect(api.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({ isSuperAdmin: true, offset: 0 }),
      ),
    );
  });

  it("makeSuperAdmin calls the API for the selected user and updates it", async () => {
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
    act(() => result.current.selectUser({ userId: 1, isSuperAdmin: false }));
    await act(async () => {
      await result.current.makeSuperAdmin();
    });
    expect(api.setSuperAdmin).toHaveBeenCalledWith(1);
    expect(result.current.selectedUser.isSuperAdmin).toBe(true);
  });

  it("revokeSuperAdminFor calls the API for the selected user and updates it", async () => {
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
    act(() => result.current.selectUser({ userId: 1, isSuperAdmin: true }));
    await act(async () => {
      await result.current.revokeSuperAdminFor();
    });
    expect(api.revokeSuperAdmin).toHaveBeenCalledWith(1);
    expect(result.current.selectedUser.isSuperAdmin).toBe(false);
  });

  it("toggleSort sets sortBy/order:asc and resets offset after a search", async () => {
    const { result } = renderHook(() => useUserAdmin());
    act(() => result.current.submitSearch());
    await waitFor(() => expect(api.getUsers).toHaveBeenCalledTimes(1));
    act(() => result.current.toggleSort("last_name"));
    await waitFor(() =>
      expect(api.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({
          sortBy: "last_name",
          order: "asc",
          offset: 0,
        }),
      ),
    );
  });

  it("toggleSort flips to desc on the second call for the same field", async () => {
    const { result } = renderHook(() => useUserAdmin());
    act(() => result.current.submitSearch());
    await waitFor(() => expect(api.getUsers).toHaveBeenCalledTimes(1));
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
