import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { useAuditLog } from "@/pages/AdminPermissions/hooks/useAuditLog";
import * as api from "@/api/adminPermissionsApi";

vi.mock("@/api/adminPermissionsApi");
vi.spyOn(toast, "error").mockImplementation(() => {});

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(toast, "error").mockImplementation(() => {});
  api.getAuditLog.mockResolvedValue({
    data: { entries: [{ id: 1 }], total: 1 },
  });
});

describe("useAuditLog", () => {
  it("fetches the feed on mount with limit 50, offset 0 and empty filters", async () => {
    const { result } = renderHook(() => useAuditLog());
    await waitFor(() => expect(result.current.entries).toHaveLength(1));
    expect(api.getAuditLog).toHaveBeenCalledWith({
      userId: undefined,
      permissionName: undefined,
      action: undefined,
      limit: 50,
      offset: 0,
    });
  });

  it("applies a filter and resets to the first page", async () => {
    api.getAuditLog.mockResolvedValue({ data: { entries: [], total: 0 } });
    const { result } = renderHook(() => useAuditLog());
    await waitFor(() => expect(api.getAuditLog).toHaveBeenCalled());
    act(() => result.current.setFilter("action", "granted"));
    await waitFor(() =>
      expect(api.getAuditLog).toHaveBeenLastCalledWith({
        userId: undefined,
        permissionName: undefined,
        action: "granted",
        limit: 50,
        offset: 0,
      }),
    );
  });

  it("calls toast.error and resets entries/total to empty on fetch failure", async () => {
    api.getAuditLog.mockRejectedValueOnce({
      response: { data: { message: "boom" } },
    });
    const { result } = renderHook(() => useAuditLog());
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("boom"));
    expect(result.current.entries).toEqual([]);
    expect(result.current.total).toBe(0);
  });
});
