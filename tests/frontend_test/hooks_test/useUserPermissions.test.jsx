import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useUserPermissions } from "@/pages/AdminPermissions/hooks/useUserPermissions";
import * as api from "@/api/adminPermissionsApi";

vi.mock("@/api/adminPermissionsApi");

const view = (active) => ({ data: { userId: 7, active, history: [] } });

describe("useUserPermissions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getUserPermissions.mockResolvedValue(view(["mentorship.round.read"]));
    api.grantPermissions.mockResolvedValue(
      view(["mentorship.round.read", "x"]),
    );
    api.revokePermissions.mockResolvedValue(view([]));
  });

  it("loads active + history for the user", async () => {
    const { result } = renderHook(() => useUserPermissions(7));
    await waitFor(() =>
      expect(result.current.active).toEqual(["mentorship.round.read"]),
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
    // checked = [x] : add "x", remove "mentorship.round.read"
    await act(async () => {
      await result.current.saveDiff(["x"]);
    });
    expect(api.grantPermissions).toHaveBeenCalledWith(7, ["x"]);
    expect(api.revokePermissions).toHaveBeenCalledWith(7, [
      "mentorship.round.read",
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
      "mentorship.round.read",
    ]);
    // mount fetch + post-save refetch
    expect(api.getUserPermissions).toHaveBeenCalledTimes(2);
  });

  it("refetches the view after a partial failure (truth over optimism)", async () => {
    const { result } = renderHook(() => useUserPermissions(7));
    await waitFor(() => expect(result.current.active).toHaveLength(1));
    api.grantPermissions.mockRejectedValueOnce(new Error("boom"));
    api.getUserPermissions.mockResolvedValueOnce(
      view(["mentorship.round.read"]),
    );
    await act(async () => {
      await result.current.saveDiff(["x"]);
    });
    // getUserPermissions called once on mount + once in the post-save refetch
    expect(api.getUserPermissions).toHaveBeenCalledTimes(2);
  });
});
