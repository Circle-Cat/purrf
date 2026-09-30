import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
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

// Latest first, as the API returns them; the first is not the lowest id.
const ROUNDS = [{ id: 7 }, { id: 3 }];

/** Renders the hook under a router at `url`, also exposing the location. */
const renderSearch = (url = "/", rounds = ROUNDS) =>
  renderHook(
    () => ({
      search: useParticipantSearch(rounds),
      location: useLocation(),
    }),
    {
      wrapper: ({ children }) => (
        <MemoryRouter initialEntries={[url]}>{children}</MemoryRouter>
      ),
    },
  );

const paramsOf = (result) =>
  new URLSearchParams(result.current.location.search);

describe("useParticipantSearch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParticipants.mockResolvedValue(page());
  });

  it("does not fetch on mount when the URL holds no search", async () => {
    const { result } = renderSearch();
    await act(async () => {});
    expect(searchParticipants).not.toHaveBeenCalled();
    expect(result.current.search.hasSearched).toBe(false);
  });

  it("fetches on mount when the URL holds a search", async () => {
    const { result } = renderSearch(
      "/?round=3&q=ali&account=active&internal=internal",
    );
    await waitFor(() => expect(result.current.search.total).toBe(1));
    expect(searchParticipants).toHaveBeenCalledWith(
      expect.objectContaining({
        q: "ali",
        accountStatus: "active",
        internal: "internal",
        roundId: "3",
        participationStatus: "participant",
        offset: 0,
      }),
    );
    expect(result.current.search.hasSearched).toBe(true);
    expect(result.current.search.q).toBe("ali");
  });

  it("changing a draft does not fetch or touch the URL", async () => {
    const { result } = renderSearch();
    act(() => result.current.search.setQ("ali"));
    act(() => result.current.search.setAccountStatus("blocked"));
    act(() => result.current.search.setInternal("external"));
    act(() => result.current.search.setRoundId("3"));
    await act(async () => {});

    expect(searchParticipants).not.toHaveBeenCalled();
    expect(result.current.location.search).toBe("");
  });

  it("submitSearch fetches with every committed filter and writes them to the URL", async () => {
    const { result } = renderSearch();
    act(() => result.current.search.setUserId("7"));
    act(() => result.current.search.setQ("  ali  "));
    act(() => result.current.search.setAccountStatus("deactivated"));
    act(() => result.current.search.setInternal("external"));
    act(() => result.current.search.setRoundId("3"));
    act(() => result.current.search.setParticipantRole("mentor"));
    act(() => result.current.search.setApprovalStatus("matched"));
    act(() => result.current.search.setOnboardingStatus("completed"));
    act(() => result.current.search.submitSearch());

    await waitFor(() => expect(result.current.search.total).toBe(1));
    expect(searchParticipants).toHaveBeenCalledTimes(1);
    expect(searchParticipants).toHaveBeenCalledWith(
      expect.objectContaining({
        userId: "7",
        q: "ali",
        accountStatus: "deactivated",
        internal: "external",
        roundId: "3",
        participantRole: "mentor",
        approvalStatus: "matched",
        onboardingStatus: "completed",
        participationStatus: "participant",
        limit: 20,
        offset: 0,
      }),
    );
    expect(Object.fromEntries(paramsOf(result))).toEqual({
      id: "7",
      q: "ali",
      account: "deactivated",
      internal: "external",
      round: "3",
      role: "mentor",
      approval: "matched",
      training: "completed",
    });
  });

  it("starts the round draft on the first round given", async () => {
    const { result } = renderSearch();
    await waitFor(() => expect(result.current.search.roundId).toBe("7"));
    expect(result.current.search.canSearch).toBe(true);
  });

  it("cannot search participants before the rounds load, or with none", async () => {
    for (const rounds of [null, []]) {
      const { result, unmount } = renderSearch("/?round=7", rounds);
      await act(async () => {});
      expect(result.current.search.canSearch).toBe(false);
      act(() => result.current.search.submitSearch());
      await act(async () => {});
      expect(searchParticipants).not.toHaveBeenCalled();
      unmount();
    }
  });

  it("treats a URL without a round as no search", async () => {
    const { result } = renderSearch("/?q=ali");
    await act(async () => {});
    expect(result.current.search.hasSearched).toBe(false);
    expect(searchParticipants).not.toHaveBeenCalled();
  });

  it("resolves a search with an empty, malformed or unknown round to the first round", async () => {
    for (const url of ["/?round=", "/?round=abc", "/?round=99"]) {
      searchParticipants.mockClear();
      const { result, unmount } = renderSearch(url);
      await waitFor(() => expect(paramsOf(result).get("round")).toBe("7"));
      expect(searchParticipants).toHaveBeenCalledTimes(1);
      expect(searchParticipants.mock.calls[0][0].roundId).toBe("7");
      expect(result.current.search.roundId).toBe("7");
      unmount();
    }
  });

  it("nextPage advances offset by limit and writes it to the URL", async () => {
    searchParticipants.mockResolvedValue(page({ total: 100 }));
    const { result } = renderSearch("/?round=7");
    await waitFor(() => expect(result.current.search.total).toBe(100));
    act(() => result.current.search.nextPage());
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ limit: 20, offset: 20 }),
      ),
    );
    expect(paramsOf(result).get("offset")).toBe("20");
  });

  it("prevPage drops the offset from the URL on the first page", async () => {
    searchParticipants.mockResolvedValue(page({ total: 100 }));
    const { result } = renderSearch("/?round=7&offset=20");
    await waitFor(() => expect(result.current.search.total).toBe(100));
    act(() => result.current.search.prevPage());
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 0 }),
      ),
    );
    expect(paramsOf(result).has("offset")).toBe(false);
  });

  it("toggleSort cycles asc, desc, then back to the default order, resetting the page", async () => {
    const { result } = renderSearch("/?round=7&offset=40");
    await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));

    act(() => result.current.search.toggleSort("user_id"));
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "user_id", order: "asc", offset: 0 }),
      ),
    );
    act(() => result.current.search.toggleSort("user_id"));
    await waitFor(() =>
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "user_id", order: "desc" }),
      ),
    );
    expect(paramsOf(result).get("order")).toBe("desc");

    act(() => result.current.search.toggleSort("user_id"));
    await waitFor(() => expect(result.current.search.sortBy).toBeNull());
    expect(searchParticipants).toHaveBeenLastCalledWith(
      expect.objectContaining({ sortBy: undefined, offset: 0 }),
    );
    expect(paramsOf(result).has("sort")).toBe(false);
  });

  it("refetch re-runs the committed search, not the drafts", async () => {
    const { result } = renderSearch("/?round=7&q=ali&sort=user_id");
    await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));
    act(() => result.current.search.setQ("bob"));

    await act(async () => {
      await result.current.search.refetch();
    });

    expect(searchParticipants).toHaveBeenCalledTimes(2);
    expect(searchParticipants).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: "ali", sortBy: "user_id", offset: 0 }),
    );
  });

  it("refetch runs silently, so it doesn't toggle loading while in flight", async () => {
    const { result } = renderSearch("/?round=7");
    await waitFor(() => expect(result.current.search.loading).toBe(false));
    await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));

    let resolveFetch;
    searchParticipants.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );
    act(() => {
      result.current.search.refetch();
    });

    expect(result.current.search.loading).toBe(false);

    await act(async () => {
      resolveFetch(page());
    });
  });

  it("ignores a superseded query's late response", async () => {
    const resolvers = [];
    searchParticipants.mockImplementation(
      () => new Promise((resolve) => resolvers.push(resolve)),
    );
    const { result } = renderSearch();
    act(() => result.current.search.submitSearch());
    await waitFor(() => expect(resolvers).toHaveLength(1));
    act(() => result.current.search.setQ("x"));
    act(() => result.current.search.submitSearch());
    await waitFor(() => expect(resolvers).toHaveLength(2));

    await act(async () => {
      resolvers[1]({ data: { participantRows: [{ userId: 2 }], total: 1 } });
    });
    await act(async () => {
      resolvers[0]({ data: { participantRows: [{ userId: 1 }], total: 1 } });
    });

    expect(result.current.search.rows).toEqual([{ userId: 2 }]);
  });
});
