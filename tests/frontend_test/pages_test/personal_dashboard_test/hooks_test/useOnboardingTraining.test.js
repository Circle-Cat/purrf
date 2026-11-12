import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { useOnboardingTraining } from "@/pages/PersonalDashboard/hooks/useOnboardingTraining";
import { getMyProfile } from "@/api/profileApi";

vi.mock("@/api/profileApi", () => ({ getMyProfile: vi.fn() }));

// Shaped like GET /profiles/me?fields=training.
const withTraining = (training) => ({ data: { profile: { training } } });

describe("useOnboardingTraining", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not fetch while disabled", () => {
    const { result } = renderHook(() =>
      useOnboardingTraining({ enabled: false }),
    );

    expect(getMyProfile).not.toHaveBeenCalled();
    expect(result.current).toEqual({ training: [], isLoading: false });
  });

  it("loads only the training section", async () => {
    const rows = [
      { id: 7, category: "mentorship_mentee_onboarding", status: "done" },
    ];
    getMyProfile.mockResolvedValue(withTraining(rows));

    const { result } = renderHook(() =>
      useOnboardingTraining({ enabled: true }),
    );

    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(getMyProfile).toHaveBeenCalledWith({ fields: ["training"] });
    expect(result.current.training).toEqual(rows);
  });

  it("settles with no rows when the fetch fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    getMyProfile.mockRejectedValue(new Error("boom"));

    const { result } = renderHook(() =>
      useOnboardingTraining({ enabled: true }),
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.training).toEqual([]);
  });
});
