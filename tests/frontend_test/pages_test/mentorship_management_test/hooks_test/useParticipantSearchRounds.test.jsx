import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useParticipantSearchRounds } from "@/pages/MentorshipManagement/hooks/useParticipantSearchRounds";
import { getAllMentorshipRounds } from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  getAllMentorshipRounds: vi.fn(),
}));

// Latest first, as the API returns them. The ids are out of time order the
// way they are on prod: round 1 is 2026 Spring, round 5 the 2024 pilot.
const TEST_ROUNDS = [
  { id: 7, name: "Mentorship 2026 Fall" },
  { id: 1, name: "Mentorship 2026 Spring" },
  { id: 2, name: "Mentorship 2025 Fall" },
  { id: 5, name: "Mentorship 2024 Pilot" },
];

describe("useParticipantSearchRounds", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches rounds on mount and keeps the order the API returns", async () => {
    getAllMentorshipRounds.mockResolvedValue({ data: TEST_ROUNDS });
    const { result } = renderHook(() => useParticipantSearchRounds());

    await waitFor(() => expect(result.current).toHaveLength(4));
    expect(result.current.map((r) => r.id)).toEqual([7, 1, 2, 5]);
    expect(getAllMentorshipRounds).toHaveBeenCalledWith();
  });

  it("falls back to an empty list if the fetch fails", async () => {
    getAllMentorshipRounds.mockRejectedValue(new Error("network error"));
    const { result } = renderHook(() => useParticipantSearchRounds());

    await waitFor(() => expect(result.current).toEqual([]));
  });
});
