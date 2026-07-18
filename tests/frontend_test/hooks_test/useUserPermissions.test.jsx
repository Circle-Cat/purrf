import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { useUserPermissions } from "@/pages/AdminPermissions/hooks/useUserPermissions";
import * as api from "@/api/adminPermissionsApi";

vi.mock("@/api/adminPermissionsApi");
vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

const view = (active) => ({ data: { userId: 7, active, history: [] } });

describe("useUserPermissions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getUserPermissions.mockResolvedValue(view(["mentorship.admin.read"]));
    api.grantPermissions.mockResolvedValue(
      view(["mentorship.admin.read", "x"]),
    );
    api.revokePermissions.mockResolvedValue(view([]));
  });

  it("loads active + history for the user", async () => {
    const { result } = renderHook(() => useUserPermissions(7));
    await waitFor(() =>
      expect(result.current.active).toEqual(["mentorship.admin.read"]),
    );
    expect(api.getUserPermissions).toHaveBeenCalledWith(7);
  });

  it("does nothing when userId is null", async () => {
    renderHook(() => useUserPermissions(null));
    expect(api.getUserPermissions).not.toHaveBeenCalled();
  });

  it("saveDiff grants newly checked and revokes unchecked", async () => {
    const { result } = renderHook(() => useUserPermissions(7));
    await waitFor(() => expect(result.current.active).toHaveLength(1));
    // checked = [x] : add "x", remove "mentorship.admin.read"
    await act(async () => {
      await result.current.saveDiff(["x"]);
    });
    expect(api.grantPermissions).toHaveBeenCalledWith(7, ["x"]);
    expect(api.revokePermissions).toHaveBeenCalledWith(7, [
      "mentorship.admin.read",
    ]);
    // mount fetch + post-save refetch
    expect(api.getUserPermissions).toHaveBeenCalledTimes(2);
  });

  it("saveDiff skips grant when nothing was added", async () => {
    const { result } = renderHook(() => useUserPermissions(7));
    await waitFor(() => expect(result.current.active).toHaveLength(1));
    await act(async () => {
      await result.current.saveDiff([]);
    });
    expect(api.grantPermissions).not.toHaveBeenCalled();
    expect(api.revokePermissions).toHaveBeenCalledWith(7, [
      "mentorship.admin.read",
    ]);
    // mount fetch + post-save refetch
    expect(api.getUserPermissions).toHaveBeenCalledTimes(2);
  });

  it("refetches the view after a partial failure (truth over optimism)", async () => {
    const { result } = renderHook(() => useUserPermissions(7));
    await waitFor(() => expect(result.current.active).toHaveLength(1));
    api.grantPermissions.mockRejectedValueOnce(new Error("boom"));
    api.getUserPermissions.mockResolvedValueOnce(
      view(["mentorship.admin.read"]),
    );
    await act(async () => {
      await result.current.saveDiff(["x"]);
    });
    // getUserPermissions called once on mount + once in the post-save refetch
    expect(api.getUserPermissions).toHaveBeenCalledTimes(2);
  });

  it("still attempts the revoke even when the grant call fails", async () => {
    const { result } = renderHook(() => useUserPermissions(7));
    await waitFor(() => expect(result.current.active).toHaveLength(1));
    api.grantPermissions.mockRejectedValueOnce(new Error("grant boom"));
    // checked = [x] : add "x" (fails), remove "mentorship.admin.read"
    await act(async () => {
      await result.current.saveDiff(["x"]);
    });
    expect(api.grantPermissions).toHaveBeenCalledWith(7, ["x"]);
    // The revoke must NOT be skipped just because the grant threw.
    expect(api.revokePermissions).toHaveBeenCalledWith(7, [
      "mentorship.admin.read",
    ]);
  });

  it("reports an error naming the failed half on a partial failure", async () => {
    const { result } = renderHook(() => useUserPermissions(7));
    await waitFor(() => expect(result.current.active).toHaveLength(1));
    api.grantPermissions.mockRejectedValueOnce(new Error("grant boom"));
    await act(async () => {
      await result.current.saveDiff(["x"]);
    });
    expect(toast.error).toHaveBeenCalledTimes(1);
    expect(toast.error.mock.calls[0][0]).toMatch(/grant/i);
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("reports success only when both grant and revoke succeed", async () => {
    const { result } = renderHook(() => useUserPermissions(7));
    await waitFor(() => expect(result.current.active).toHaveLength(1));
    await act(async () => {
      await result.current.saveDiff(["x"]);
    });
    expect(toast.success).toHaveBeenCalledWith("Permissions updated");
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("surfaces the backend message when a permission call fails", async () => {
    const { result } = renderHook(() => useUserPermissions(7));
    await waitFor(() => expect(result.current.active).toHaveLength(1));
    api.revokePermissions.mockRejectedValueOnce({
      response: { data: { message: "Cannot revoke a super-admin grant" } },
    });
    await act(async () => {
      await result.current.saveDiff(["x"]);
    });
    expect(toast.error).toHaveBeenCalledWith(
      "Cannot revoke a super-admin grant",
    );
  });

  it("ignores a previous user's late response so saveDiff uses the current baseline", async () => {
    // Control resolution order per user id.
    const resolvers = {};
    api.getUserPermissions.mockImplementation(
      (id) =>
        new Promise((resolve) => {
          resolvers[id] = resolve;
        }),
    );

    const { result, rerender } = renderHook(
      ({ id }) => useUserPermissions(id),
      {
        initialProps: { id: 1 },
      },
    );
    await waitFor(() => expect(resolvers[1]).toBeDefined());

    // Switch to user 2 before user 1's permissions come back.
    rerender({ id: 2 });
    await waitFor(() => expect(resolvers[2]).toBeDefined());

    // Newer user (2) resolves first.
    await act(async () => {
      resolvers[2]({ data: { active: ["perm.b"], history: [] } });
    });
    // Stale user (1) resolves last — must NOT overwrite user 2's baseline.
    await act(async () => {
      resolvers[1]({ data: { active: ["perm.a"], history: [] } });
    });

    expect(result.current.active).toEqual(["perm.b"]);
  });
});
