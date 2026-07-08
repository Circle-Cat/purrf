import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useParticipantSearch } from "@/pages/MentorshipManagement/hooks/useParticipantSearch";
import { searchParticipants } from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  searchParticipants: vi.fn(),
}));

const page = (overrides = {}) => ({
  data: {
    participantRows: [{ userId: 1, firstName: "Alice", lastName: "Doe" }],
    total: 1,
    ...overrides,
  },
});

describe("useParticipantSearch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParticipants.mockResolvedValue(page());
  });

  it("does not fetch on mount and reports hasSearched=false in participant mode", async () => {
    const { result } = renderHook(() => useParticipantSearch("participant"));
    await act(async () => {});
    expect(searchParticipants).not.toHaveBeenCalled();
    expect(result.current.hasSearched).toBe(false);
  });

  it("does not fetch on mount and reports hasSearched=false in non-participant mode", async () => {
    const { result } = renderHook(() =>
      useParticipantSearch("non_participant"),
    );
    await act(async () => {});
    expect(searchParticipants).not.toHaveBeenCalled();
    expect(result.current.hasSearched).toBe(false);
  });

  it("submitSearch fetches with participationStatus=participant and all committed filters", async () => {
    const { result } = renderHook(() => useParticipantSearch("participant"));
    act(() => result.current.setRoundId("3"));
    act(() => result.current.setParticipantRole("mentor"));
    act(() => result.current.setApprovalStatus("matched"));
    act(() => result.current.setOnboardingStatus("completed"));
    act(() => result.current.submitSearch());
    await waitFor(() => expect(result.current.total).toBe(1));
    expect(searchParticipants).toHaveBeenCalledWith(
      expect.objectContaining({
        roundId: "3",
        participantRole: "mentor",
        approvalStatus: "matched",
        onboardingStatus: "completed",
        participationStatus: "participant",
        limit: 20,
        offset: 0,
      }),
    );
    expect(result.current.hasSearched).toBe(true);
  });

  it("submitSearch fetches with participationStatus=non_participant, limit 20, offset 0", async () => {
    const { result } = renderHook(() =>
      useParticipantSearch("non_participant"),
    );
    act(() => result.current.setName("Alice"));
    act(() => result.current.submitSearch());
    await waitFor(() => expect(result.current.total).toBe(1));
    expect(searchParticipants).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Alice",
        participationStatus: "non_participant",
        limit: 20,
        offset: 0,
      }),
    );
    expect(result.current.hasSearched).toBe(true);
  });

  it("does not send round/role/approval/matchedUser filters in non-participant mode", async () => {
    const { result } = renderHook(() =>
      useParticipantSearch("non_participant"),
    );
    act(() => result.current.submitSearch());
    await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));
    const callArgs = searchParticipants.mock.calls[0][0];
    expect(callArgs).not.toHaveProperty("roundId");
    expect(callArgs).not.toHaveProperty("participantRole");
    expect(callArgs).not.toHaveProperty("approvalStatus");
    expect(callArgs).not.toHaveProperty("matchedUser");
  });

  it("sends the onboardingStatus filter in non-participant mode", async () => {
    const { result } = renderHook(() =>
      useParticipantSearch("non_participant"),
    );
    act(() => result.current.setOnboardingStatus("completed"));
    act(() => result.current.submitSearch());
    await waitFor(() => expect(result.current.total).toBe(1));
    expect(searchParticipants).toHaveBeenCalledWith(
      expect.objectContaining({
        onboardingStatus: "completed",
        participationStatus: "non_participant",
      }),
    );
  });

  it("nextPage advances offset by limit after a search", async () => {
    searchParticipants.mockResolvedValue(page({ total: 100 }));
    const { result } = renderHook(() => useParticipantSearch("participant"));
    act(() => result.current.submitSearch());
    await waitFor(() => expect(result.current.total).toBe(100));
    act(() => result.current.nextPage());
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ limit: 20, offset: 20 }),
      ),
    );
  });

  it("toggleSort sets sortBy/order:asc and resets offset after a search", async () => {
    const { result } = renderHook(() => useParticipantSearch("participant"));
    act(() => result.current.submitSearch());
    await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));
    act(() => result.current.toggleSort("user_id"));
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "user_id", order: "asc", offset: 0 }),
      ),
    );
  });

  it("toggleSort flips to desc on the second call for the same field", async () => {
    const { result } = renderHook(() => useParticipantSearch("participant"));
    act(() => result.current.submitSearch());
    await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));
    act(() => result.current.toggleSort("user_id"));
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "user_id", order: "asc" }),
      ),
    );
    act(() => result.current.toggleSort("user_id"));
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "user_id", order: "desc" }),
      ),
    );
  });

  it("toggleSort clears the sort back to the default order on the third call", async () => {
    const { result } = renderHook(() => useParticipantSearch("participant"));
    act(() => result.current.submitSearch());
    await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));
    act(() => result.current.toggleSort("user_id"));
    await waitFor(() => expect(result.current.sortBy).toBe("user_id"));
    act(() => result.current.toggleSort("user_id"));
    await waitFor(() => expect(result.current.order).toBe("desc"));

    act(() => result.current.toggleSort("user_id"));

    await waitFor(() => expect(result.current.sortBy).toBeNull());
    expect(searchParticipants).toHaveBeenLastCalledWith(
      expect.objectContaining({ sortBy: undefined, offset: 0 }),
    );
  });

  it("ignores a superseded query's late response", async () => {
    const resolvers = [];
    searchParticipants.mockImplementation(
      () => new Promise((resolve) => resolvers.push(resolve)),
    );
    const { result } = renderHook(() => useParticipantSearch("participant"));
    act(() => result.current.submitSearch());
    await waitFor(() => expect(resolvers).toHaveLength(1));
    act(() => result.current.setName("x"));
    act(() => result.current.submitSearch());
    await waitFor(() => expect(resolvers).toHaveLength(2));

    await act(async () => {
      resolvers[1]({ data: { participantRows: [{ userId: 2 }], total: 1 } });
    });
    await act(async () => {
      resolvers[0]({ data: { participantRows: [{ userId: 1 }], total: 1 } });
    });

    expect(result.current.rows).toEqual([{ userId: 2 }]);
  });
});
