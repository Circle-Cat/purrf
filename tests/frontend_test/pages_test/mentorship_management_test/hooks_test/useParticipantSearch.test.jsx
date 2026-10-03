import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { useParticipantSearch } from "@/pages/MentorshipManagement/hooks/useParticipantSearch";
import { searchParticipants, searchUnregistered } from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  searchParticipants: vi.fn(),
  searchUnregistered: vi.fn(),
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
const renderSearch = (url = "/", rounds = ROUNDS, registrationRoundId) =>
  renderHook(
    () => ({
      search: useParticipantSearch(rounds, registrationRoundId),
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

  describe("Not registered", () => {
    // Round 7 is the one taking registrations; round 3 is not.
    const open = (url) => renderSearch(url, ROUNDS, "7");

    beforeEach(() => {
      searchUnregistered.mockResolvedValue({
        data: { rows: [{ userId: 9, admittedRoles: ["mentee"] }], total: 1 },
      });
    });

    it("lists the round's not registered people with the person filters and admitted role", async () => {
      const { result } = open(
        "/?round=7&q=ali&role=mentee&training=completed&approval=matched",
      );
      await waitFor(() => expect(result.current.search.total).toBe(1));
      expect(result.current.search.canListNotRegistered).toBe(true);

      act(() => result.current.search.toggleNotRegistered());

      await waitFor(() => expect(searchUnregistered).toHaveBeenCalled());
      expect(searchUnregistered).toHaveBeenCalledWith("7", {
        userId: undefined,
        q: "ali",
        accountStatus: undefined,
        internal: undefined,
        admittedRole: "mentee",
        limit: 20,
        offset: 0,
        order: "asc",
      });
      const params = paramsOf(result);
      expect(params.get("notRegistered")).toBe("1");
      expect(params.has("training")).toBe(false);
      expect(params.has("approval")).toBe(false);
      expect(result.current.search.onboardingStatus).toBe("");
      expect(result.current.search.approvalStatus).toBe("");
      await waitFor(() =>
        expect(result.current.search.rows).toEqual([
          { userId: 9, admittedRoles: ["mentee"] },
        ]),
      );
      expect(result.current.search.notRegistered).toBe(true);
    });

    it("drops a URL request for it in a round not taking registrations", async () => {
      const { result } = open("/?round=3&notRegistered=1");

      await waitFor(() =>
        expect(paramsOf(result).has("notRegistered")).toBe(false),
      );
      expect(result.current.search.notRegistered).toBe(false);
      expect(result.current.search.canListNotRegistered).toBe(false);
      expect(searchUnregistered).not.toHaveBeenCalled();
      expect(searchParticipants).toHaveBeenCalled();
    });

    it("will not go in for a round not taking registrations", async () => {
      const { result } = open("/?round=3");
      await waitFor(() => expect(result.current.search.total).toBe(1));

      act(() => result.current.search.toggleNotRegistered());
      await act(async () => {});

      expect(paramsOf(result).has("notRegistered")).toBe(false);
      expect(searchUnregistered).not.toHaveBeenCalled();
    });

    it("stays in it on Search in the same round and leaves it for another round", async () => {
      const { result } = open("/?round=7&notRegistered=1");
      await waitFor(() => expect(searchUnregistered).toHaveBeenCalledTimes(1));

      act(() => result.current.search.setQ("bo"));
      act(() => result.current.search.submitSearch());
      await waitFor(() => expect(searchUnregistered).toHaveBeenCalledTimes(2));
      expect(paramsOf(result).get("notRegistered")).toBe("1");

      act(() => result.current.search.setRoundId("3"));
      act(() => result.current.search.submitSearch());

      await waitFor(() => expect(paramsOf(result).get("round")).toBe("3"));
      expect(paramsOf(result).has("notRegistered")).toBe(false);
      expect(result.current.search.notRegistered).toBe(false);
    });

    it("toggling again goes back to the participants", async () => {
      const { result } = open("/?round=7&notRegistered=1");
      await waitFor(() =>
        expect(result.current.search.notRegistered).toBe(true),
      );
      searchParticipants.mockClear();

      act(() => result.current.search.toggleNotRegistered());

      await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));
      expect(paramsOf(result).has("notRegistered")).toBe(false);
      expect(result.current.search.notRegistered).toBe(false);
    });

    it("waits for the registration round before reading a Not registered link", async () => {
      const { result, rerender } = renderHook(
        ({ registrationRoundId }) => ({
          search: useParticipantSearch(ROUNDS, registrationRoundId),
          location: useLocation(),
        }),
        {
          initialProps: { registrationRoundId: undefined },
          wrapper: ({ children }) => (
            <MemoryRouter initialEntries={["/?round=7&notRegistered=1"]}>
              {children}
            </MemoryRouter>
          ),
        },
      );
      await act(async () => {});

      expect(searchParticipants).not.toHaveBeenCalled();
      expect(searchUnregistered).not.toHaveBeenCalled();
      expect(paramsOf(result).get("notRegistered")).toBe("1");
      expect(result.current.search.loading).toBe(true);

      rerender({ registrationRoundId: "7" });

      await waitFor(() => expect(searchUnregistered).toHaveBeenCalledTimes(1));
      expect(searchParticipants).not.toHaveBeenCalled();
    });

    it("offers nothing when no round is taking registrations", async () => {
      const { result } = renderSearch("/?round=7", ROUNDS, null);
      await waitFor(() => expect(result.current.search.total).toBe(1));

      expect(result.current.search.canListNotRegistered).toBe(false);
    });
  });
});
