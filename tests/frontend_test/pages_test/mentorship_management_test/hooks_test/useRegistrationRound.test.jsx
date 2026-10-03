import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useRegistrationRound } from "@/pages/MentorshipManagement/hooks/useRegistrationRound";
import { getMentorshipRoundSlots } from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  getMentorshipRoundSlots: vi.fn(),
}));

describe("useRegistrationRound", () => {
  beforeEach(() => vi.clearAllMocks());

  it("is undefined until the slots load, then the open round's id", async () => {
    getMentorshipRoundSlots.mockResolvedValue({
      data: { registrationRoundId: 7, isRegistrationOpen: true },
    });

    const { result } = renderHook(() => useRegistrationRound());

    expect(result.current).toBeUndefined();
    await waitFor(() => expect(result.current).toBe("7"));
  });

  it("is null when the registration round is not open", async () => {
    getMentorshipRoundSlots.mockResolvedValue({
      data: { registrationRoundId: 7, isRegistrationOpen: false },
    });

    const { result } = renderHook(() => useRegistrationRound());

    await waitFor(() => expect(result.current).toBeNull());
  });

  it("is null when the slots cannot be read", async () => {
    getMentorshipRoundSlots.mockRejectedValue(new Error("boom"));

    const { result } = renderHook(() => useRegistrationRound());

    await waitFor(() => expect(result.current).toBeNull());
  });
});
