import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { useLeaveCoverage } from "@/pages/Leave/hooks/useLeaveCoverage";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");

const envelope = (isCovered) => ({
  success: true,
  message: "ok",
  data: { isCovered },
});

describe("useLeaveCoverage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not claim coverage while loading", () => {
    api.getLeaveCoverage.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useLeaveCoverage());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.isCovered).toBe(false);
  });

  it("does not claim coverage after a failed load", async () => {
    // Fails closed: offering a screen we could not confirm is worse than
    // making somebody covered wait a moment.
    api.getLeaveCoverage.mockRejectedValue(new Error("network error"));

    const { result } = renderHook(() => useLeaveCoverage());

    await waitFor(() => expect(result.current.loadError).toBe(true));
    expect(result.current.isCovered).toBe(false);
  });

  it("reports coverage the server confirms", async () => {
    api.getLeaveCoverage.mockResolvedValue(envelope(true));

    const { result } = renderHook(() => useLeaveCoverage());

    await waitFor(() => expect(result.current.isCovered).toBe(true));
  });

  it("reports no coverage when the server says so", async () => {
    api.getLeaveCoverage.mockResolvedValue(envelope(false));

    const { result } = renderHook(() => useLeaveCoverage());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isCovered).toBe(false);
  });

  it("asks nothing while the feature is switched off", () => {
    const { result } = renderHook(() => useLeaveCoverage({ enabled: false }));

    expect(api.getLeaveCoverage).not.toHaveBeenCalled();
    expect(result.current.isCovered).toBe(false);
  });
});
