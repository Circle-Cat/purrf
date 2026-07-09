import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useParticipantSearchRounds } from "@/pages/MentorshipManagement/hooks/useParticipantSearchRounds";
import { getAllMentorshipRounds } from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  getAllMentorshipRounds: vi.fn(),
}));

const TEST_ROUNDS = [
  { id: 1, name: "Spring 2025" },
  { id: 3, name: "Spring 2026" },
  { id: 2, name: "Fall 2025" },
];

describe("useParticipantSearchRounds", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches rounds on mount, sorted by id descending", async () => {
    getAllMentorshipRounds.mockResolvedValue({ data: TEST_ROUNDS });
    const { result } = renderHook(() => useParticipantSearchRounds());

    await waitFor(() => expect(result.current).toHaveLength(3));
    expect(result.current.map((r) => r.id)).toEqual([3, 2, 1]);
    expect(getAllMentorshipRounds).toHaveBeenCalledWith();
  });

  it("falls back to an empty list if the fetch fails", async () => {
    getAllMentorshipRounds.mockRejectedValue(new Error("network error"));
    const { result } = renderHook(() => useParticipantSearchRounds());

    await waitFor(() => expect(result.current).toEqual([]));
  });
});
