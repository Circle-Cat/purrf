import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation, useNavigationType } from "react-router-dom";
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
// Round 7 is in progress; round 3 is not.
const ROUNDS = [
  { id: 7, isInProgress: true },
  { id: 3, isInProgress: false },
];

/** Renders the hook under a router at `url`, also exposing the location. */
const renderSearch = (url = "/", rounds = ROUNDS, options) =>
  renderHook(
    () => ({
      search: useParticipantSearch(rounds, options),
      location: useLocation(),
      navigationType: useNavigationType(),
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

  describe("Eligible for matching", () => {
    const open = (url) => renderSearch(url);

    it("picking it changes nothing until Search, which sends eligible", async () => {
      const { result } = open("/?round=7");
      await waitFor(() => expect(result.current.search.total).toBe(1));
      expect(result.current.search.canListEligible).toBe(true);

      act(() => result.current.search.setListEligible(true));
      await act(async () => {});
      expect(searchParticipants).toHaveBeenCalledTimes(1);
      expect(paramsOf(result).has("eligible")).toBe(false);

      act(() => result.current.search.submitSearch());

      await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(2));
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ roundId: "7", eligible: true }),
      );
      expect(paramsOf(result).get("eligible")).toBe("1");
      expect(result.current.search.eligible).toBe(true);
    });

    it("keeps eligible while paging", async () => {
      searchParticipants.mockResolvedValue(page({ total: 45 }));
      const { result } = open("/?round=7&eligible=1");
      await waitFor(() => expect(result.current.search.total).toBe(45));

      act(() => result.current.search.nextPage());

      await waitFor(() => expect(paramsOf(result).get("offset")).toBe("20"));
      expect(paramsOf(result).get("eligible")).toBe("1");
    });

    it("cannot be picked for a round not in progress", async () => {
      const { result } = open("/?round=3");
      await waitFor(() => expect(result.current.search.total).toBe(1));

      act(() => result.current.search.setListEligible(true));

      expect(result.current.search.canListEligible).toBe(false);
      expect(result.current.search.listEligible).toBe(false);
    });

    it("goes back to Registered when a round not in progress is picked", async () => {
      const { result } = open("/?round=7&eligible=1");
      await waitFor(() =>
        expect(result.current.search.listEligible).toBe(true),
      );

      act(() => result.current.search.setRoundId("3"));

      expect(result.current.search.listEligible).toBe(false);
    });

    it("is one choice with Not registered: picking either leaves the other", async () => {
      const { result } = open("/?round=7&eligible=1");
      await waitFor(() =>
        expect(result.current.search.listEligible).toBe(true),
      );

      act(() => result.current.search.setListNotRegistered(true));
      expect(result.current.search.listEligible).toBe(false);
      expect(result.current.search.listNotRegistered).toBe(true);

      act(() => result.current.search.setListEligible(true));
      expect(result.current.search.listEligible).toBe(true);
      expect(result.current.search.listNotRegistered).toBe(false);
    });

    it("drops a URL request for it in a round not in progress", async () => {
      const { result } = open("/?round=3&eligible=1");

      await waitFor(() => expect(paramsOf(result).has("eligible")).toBe(false));
      expect(result.current.search.eligible).toBe(false);
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ eligible: undefined }),
      );
    });
  });

  describe("Needs exemption", () => {
    const open = (url) => renderSearch(url);

    it("is asked for from the URL and kept while paging", async () => {
      searchParticipants.mockResolvedValue(page({ total: 45 }));
      const { result } = open("/?round=7&needsExemption=1");
      await waitFor(() => expect(result.current.search.total).toBe(45));

      expect(result.current.search.needsExemption).toBe(true);
      expect(searchParticipants).toHaveBeenLastCalledWith(
        expect.objectContaining({ needsExemption: true, eligible: undefined }),
      );
      act(() => result.current.search.nextPage());

      await waitFor(() => expect(paramsOf(result).get("offset")).toBe("20"));
      expect(paramsOf(result).get("needsExemption")).toBe("1");
    });

    it("is one choice with the other lists", async () => {
      const { result } = open("/?round=7&eligible=1");
      await waitFor(() =>
        expect(result.current.search.listEligible).toBe(true),
      );

      act(() => result.current.search.setListNeedsExemption(true));
      expect(result.current.search.listNeedsExemption).toBe(true);
      expect(result.current.search.listEligible).toBe(false);

      act(() => result.current.search.setListNotRegistered(true));
      expect(result.current.search.listNeedsExemption).toBe(false);
    });

    it("cannot be picked for, and is dropped from, a round not in progress", async () => {
      const { result } = open("/?round=3&needsExemption=1");

      await waitFor(() =>
        expect(paramsOf(result).has("needsExemption")).toBe(false),
      );
      expect(result.current.search.needsExemption).toBe(false);
      act(() => result.current.search.setListNeedsExemption(true));
      expect(result.current.search.canListNeedsExemption).toBe(false);
      expect(result.current.search.listNeedsExemption).toBe(false);
    });

    it("searching it writes it to the URL", async () => {
      const { result } = open("/?round=7");
      await waitFor(() => expect(result.current.search.total).toBe(1));

      act(() => result.current.search.setListNeedsExemption(true));
      act(() => result.current.search.submitSearch());

      await waitFor(() =>
        expect(paramsOf(result).get("needsExemption")).toBe("1"),
      );
    });
  });

  describe("Not registered", () => {
    const open = (url) => renderSearch(url);

    beforeEach(() => {
      searchUnregistered.mockResolvedValue({
        data: { rows: [{ userId: 9, admittedRoles: ["mentee"] }], total: 1 },
      });
    });

    it("picking it changes nothing until Search", async () => {
      const { result } = open("/?round=7");
      await waitFor(() => expect(result.current.search.total).toBe(1));

      act(() => result.current.search.setListNotRegistered(true));
      await act(async () => {});

      expect(result.current.search.listNotRegistered).toBe(true);
      expect(result.current.search.notRegistered).toBe(false);
      expect(paramsOf(result).has("notRegistered")).toBe(false);
      expect(searchUnregistered).not.toHaveBeenCalled();
      expect(searchParticipants).toHaveBeenCalledTimes(1);
    });

    it("lists the round's not registered people with the person filters and admitted role on Search", async () => {
      const { result } = open(
        "/?round=7&q=ali&role=mentee&training=completed&approval=matched",
      );
      await waitFor(() => expect(result.current.search.total).toBe(1));
      expect(result.current.search.canListNotRegistered).toBe(true);

      act(() => result.current.search.setListNotRegistered(true));
      expect(result.current.search.onboardingStatus).toBe("");
      expect(result.current.search.approvalStatus).toBe("");
      act(() => result.current.search.submitSearch());

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

    it("cannot be picked for a round not taking registrations", async () => {
      const { result } = open("/?round=3");
      await waitFor(() => expect(result.current.search.total).toBe(1));

      act(() => result.current.search.setListNotRegistered(true));
      act(() => result.current.search.submitSearch());
      await act(async () => {});

      expect(result.current.search.listNotRegistered).toBe(false);
      expect(paramsOf(result).has("notRegistered")).toBe(false);
      expect(searchUnregistered).not.toHaveBeenCalled();
    });

    it("stays in it on Search in the same round and goes back to Registered when another round is picked", async () => {
      const { result } = open("/?round=7&notRegistered=1");
      await waitFor(() => expect(searchUnregistered).toHaveBeenCalledTimes(1));
      expect(result.current.search.listNotRegistered).toBe(true);

      act(() => result.current.search.setQ("bo"));
      act(() => result.current.search.submitSearch());
      await waitFor(() => expect(searchUnregistered).toHaveBeenCalledTimes(2));
      expect(paramsOf(result).get("notRegistered")).toBe("1");

      act(() => result.current.search.setRoundId("3"));
      expect(result.current.search.listNotRegistered).toBe(false);
      expect(result.current.search.notRegistered).toBe(true);
      act(() => result.current.search.submitSearch());

      await waitFor(() => expect(paramsOf(result).get("round")).toBe("3"));
      expect(paramsOf(result).has("notRegistered")).toBe(false);
      expect(result.current.search.notRegistered).toBe(false);
    });

    it("picking Registered and searching goes back to the participants", async () => {
      const { result } = open("/?round=7&notRegistered=1");
      await waitFor(() =>
        expect(result.current.search.notRegistered).toBe(true),
      );
      searchParticipants.mockClear();

      act(() => result.current.search.setListNotRegistered(false));
      await act(async () => {});
      expect(searchParticipants).not.toHaveBeenCalled();
      act(() => result.current.search.submitSearch());

      await waitFor(() => expect(searchParticipants).toHaveBeenCalledTimes(1));
      expect(paramsOf(result).has("notRegistered")).toBe(false);
      expect(result.current.search.notRegistered).toBe(false);
    });

    it("waits for the rounds before reading a Not registered link", async () => {
      const { result, rerender } = renderHook(
        ({ rounds }) => ({
          search: useParticipantSearch(rounds),
          location: useLocation(),
        }),
        {
          initialProps: { rounds: null },
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

      rerender({ rounds: ROUNDS });

      await waitFor(() => expect(searchUnregistered).toHaveBeenCalledTimes(1));
      expect(searchParticipants).not.toHaveBeenCalled();
      expect(result.current.search.listNotRegistered).toBe(true);
    });

    it("offers nothing when the round is not in progress", async () => {
      const { result } = renderSearch("/?round=3");
      await waitFor(() => expect(result.current.search.total).toBe(1));

      expect(result.current.search.canListNotRegistered).toBe(false);
      expect(result.current.search.canListEligible).toBe(false);
    });
  });

  it("keeps the list key through paging and sorting, and changes it with the list", async () => {
    searchParticipants.mockResolvedValue(page({ total: 45 }));
    const { result } = renderSearch("/?round=7&eligible=1");
    await waitFor(() => expect(result.current.search.total).toBe(45));
    const key = result.current.search.listKey;
    expect(key).not.toBe("");
    expect(result.current.search.committedRoundId).toBe("7");

    act(() => result.current.search.nextPage());
    await waitFor(() => expect(paramsOf(result).get("offset")).toBe("20"));
    act(() => result.current.search.toggleSort("user_id"));
    await waitFor(() => expect(paramsOf(result).get("sort")).toBe("user_id"));
    expect(result.current.search.listKey).toBe(key);

    act(() => result.current.search.setQ("ali"));
    expect(result.current.search.listKey).toBe(key);
    act(() => result.current.search.submitSearch());
    await waitFor(() => expect(paramsOf(result).get("q")).toBe("ali"));
    expect(result.current.search.listKey).not.toBe(key);
  });

  describe("a page past the end", () => {
    it("moves to the last page with rows, replacing the history entry", async () => {
      searchParticipants.mockResolvedValue(page({ total: 25 }));
      const { result } = renderSearch("/?round=7&offset=40");
      await waitFor(() => expect(paramsOf(result).get("offset")).toBe("20"));
      await waitFor(() =>
        expect(searchParticipants).toHaveBeenLastCalledWith(
          expect.objectContaining({ offset: 20 }),
        ),
      );
      await act(async () => {});
      expect(paramsOf(result).get("round")).toBe("7");
      expect(result.current.navigationType).toBe("REPLACE");
      expect(searchParticipants).toHaveBeenCalledTimes(2);
    });

    it("drops the offset when nothing is left", async () => {
      searchParticipants.mockResolvedValue(page({ total: 0 }));
      const { result } = renderSearch("/?round=7&offset=20");
      await waitFor(() => expect(paramsOf(result).has("offset")).toBe(false));
      expect(paramsOf(result).get("round")).toBe("7");
    });

    it("leaves a page within range alone", async () => {
      searchParticipants.mockResolvedValue(page({ total: 25 }));
      const { result } = renderSearch("/?round=7&offset=20");
      await waitFor(() => expect(result.current.search.total).toBe(25));
      await act(async () => {});
      expect(paramsOf(result).get("offset")).toBe("20");
      expect(searchParticipants).toHaveBeenCalledTimes(1);
    });
  });

  describe("Notification filter", () => {
    const ON = { notificationsOn: true };

    it("commits to the URL and sends both halves", async () => {
      const { result } = renderSearch("/", ROUNDS, ON);
      act(() =>
        result.current.search.setNotification({
          stage: "midterm_reminder",
          state: "not_notified",
        }),
      );
      act(() => result.current.search.submitSearch());
      await waitFor(() =>
        expect(searchParticipants).toHaveBeenCalledWith(
          expect.objectContaining({
            notificationStage: "midterm_reminder",
            notificationState: "not_notified",
          }),
        ),
      );
      expect(paramsOf(result).get("notifyStage")).toBe("midterm_reminder");
      expect(paramsOf(result).get("notifyState")).toBe("not_notified");
      expect(result.current.search.notificationFiltered).toBe(true);
    });

    it("reads it back from the URL into the draft", async () => {
      const { result } = renderSearch(
        "/?round=7&notifyStage=admission&notifyState=notified",
        ROUNDS,
        ON,
      );
      await waitFor(() => expect(searchParticipants).toHaveBeenCalled());
      expect(result.current.search.notification).toEqual({
        stage: "admission",
        state: "notified",
      });
    });

    it("ignores half a filter or unknown values", async () => {
      for (const query of [
        "notifyStage=admission",
        "notifyStage=admission&notifyState=replied",
        "notifyStage=rejected&notifyState=notified",
      ]) {
        searchParticipants.mockClear();
        renderSearch(`/?round=7&${query}`, ROUNDS, ON);
        await waitFor(() => expect(searchParticipants).toHaveBeenCalled());
        expect(searchParticipants.mock.calls[0][0].notificationStage).toBe(
          undefined,
        );
      }
    });

    it("does not send the notification filter while notifications are off", async () => {
      const { result } = renderSearch(
        "/?round=7&notifyStage=admission&notifyState=notified",
      );
      await waitFor(() => expect(searchParticipants).toHaveBeenCalled());
      expect(searchParticipants.mock.calls[0][0].notificationStage).toBe(
        undefined,
      );
      expect(result.current.search.notificationFiltered).toBe(false);
    });

    it("does not write the filter back when paging while notifications are off", async () => {
      searchParticipants.mockResolvedValue(page({ total: 100 }));
      const { result } = renderSearch(
        "/?round=7&notifyStage=admission&notifyState=notified",
      );
      await waitFor(() => expect(result.current.search.total).toBe(100));
      act(() => result.current.search.nextPage());
      await waitFor(() => expect(paramsOf(result).get("offset")).toBe("20"));
      expect(paramsOf(result).has("notifyStage")).toBe(false);
      expect(paramsOf(result).has("notifyState")).toBe(false);
    });

    it("does not write the filter back on search while notifications are off", async () => {
      const { result } = renderSearch(
        "/?round=7&notifyStage=admission&notifyState=notified",
      );
      await waitFor(() => expect(searchParticipants).toHaveBeenCalled());
      act(() => result.current.search.setQ("ali"));
      act(() => result.current.search.submitSearch());
      await waitFor(() => expect(paramsOf(result).get("q")).toBe("ali"));
      expect(paramsOf(result).has("notifyStage")).toBe(false);
      expect(paramsOf(result).has("notifyState")).toBe(false);
    });

    it("sends it with the Not registered list", async () => {
      searchUnregistered.mockResolvedValue({ data: { rows: [], total: 0 } });
      renderSearch(
        "/?round=7&notRegistered=1&notifyStage=round_recruitment&notifyState=not_notified",
        ROUNDS,
        ON,
      );
      await waitFor(() =>
        expect(searchUnregistered).toHaveBeenCalledWith(
          "7",
          expect.objectContaining({
            notificationStage: "round_recruitment",
            notificationState: "not_notified",
          }),
        ),
      );
    });

    it("drops a stage the next list does not offer, and all of it for Eligible", async () => {
      const { result } = renderSearch("/", ROUNDS, ON);
      act(() =>
        result.current.search.setNotification({
          stage: "match_result",
          state: "notified",
        }),
      );
      act(() => result.current.search.setListNotRegistered(true));
      expect(result.current.search.notification).toEqual({
        stage: "",
        state: "",
      });

      act(() =>
        result.current.search.setNotification({
          stage: "admission",
          state: "notified",
        }),
      );
      act(() => result.current.search.setListNotRegistered(false));
      expect(result.current.search.notification.stage).toBe("admission");

      act(() => result.current.search.setListEligible(true));
      expect(result.current.search.notification).toEqual({
        stage: "",
        state: "",
      });
    });

    it("changes the list key with the filter", async () => {
      const { result } = renderSearch("/?round=7", ROUNDS, ON);
      await waitFor(() => expect(searchParticipants).toHaveBeenCalled());
      const before = result.current.search.listKey;
      act(() =>
        result.current.search.setNotification({
          stage: "admission",
          state: "scheduled",
        }),
      );
      act(() => result.current.search.submitSearch());
      await waitFor(() =>
        expect(result.current.search.listKey).not.toBe(before),
      );
    });
  });
});
