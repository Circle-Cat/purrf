import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { searchParticipants, searchUnregistered } from "@/api/mentorshipApi";
import { useRequestGuard } from "@/hooks/useRequestGuard";

const LIMIT = 20;

/**
 * Query-string keys. The committed search lives in the URL so a search can be
 * shared as a link, and back/forward and reload land on the same list. Search
 * always writes `round`, so its presence is what marks one as run.
 */
export const PARAM = Object.freeze({
  ID: "id",
  Q: "q",
  ACCOUNT: "account",
  INTERNAL: "internal",
  TRAINING: "training",
  ROUND: "round",
  ROLE: "role",
  APPROVAL: "approval",
  SORT: "sort",
  ORDER: "order",
  OFFSET: "offset",
  NOT_REGISTERED: "notRegistered",
  ELIGIBLE: "eligible",
});

const ACCOUNT_STATUSES = ["active", "blocked", "deactivated"];
const INTERNAL_VALUES = ["internal", "external"];
const ONBOARDING_STATUSES = ["completed", "incomplete"];

const readDigits = (params, key) => {
  const raw = params.get(key) ?? "";
  return /^\d+$/.test(raw) ? raw : "";
};

const readOneOf = (params, key, allowed) => {
  const raw = params.get(key) ?? "";
  return allowed.includes(raw) ? raw : "";
};

/**
 * Owns the participant search.
 *
 * The inputs are drafts: nothing is fetched when they change, only when
 * submitSearch() (the Search button) writes them to the URL. The list follows
 * the URL: with no search there it stays empty and nothing is requested.
 * Paging and sorting move within the committed search and also go through the
 * URL.
 *
 * A search always runs within one round. The default is the first of `rounds`
 * (the API lists the latest first). A search whose round is not in `rounds`
 * is read as the default round and rewritten to say so. Until `rounds` has
 * loaded, or when there are none, nothing is fetched and `canSearch` is false.
 *
 * The List filter picks who is listed: everyone registered (the default),
 * only those eligible for matching, or the Not registered list -- the people
 * admitted to the programme who have not registered for the round. Like the
 * other filters it is a draft until Search. Eligible and Not registered are
 * only on offer for a round in progress, which the round list says
 * (`isInProgress`): picking a round not in progress puts the draft back to
 * Registered, and a URL asking for either in such a round is rewritten
 * without it. In Not registered the role filter means the admitted role, and
 * training and approval do not apply.
 *
 * @param {Array<{id: number, isInProgress?: boolean}>|null} rounds - Rounds,
 *   latest first; null while loading.
 */
export const useParticipantSearch = (rounds) => {
  const [searchParams, setSearchParams] = useSearchParams();

  const hasSearched = searchParams.has(PARAM.ROUND);
  const params = hasSearched ? searchParams : new URLSearchParams();

  const roundIds = rounds ? rounds.map((r) => String(r.id)) : [];
  const defaultRoundId = roundIds[0] ?? "";
  const urlRoundId = params.get(PARAM.ROUND) ?? "";
  const canSearch = defaultRoundId !== "";

  const committedUserId = readDigits(params, PARAM.ID);
  const committedQ = params.get(PARAM.Q) ?? "";
  const committedAccount = readOneOf(params, PARAM.ACCOUNT, ACCOUNT_STATUSES);
  const committedInternal = readOneOf(params, PARAM.INTERNAL, INTERNAL_VALUES);
  const committedOnboarding = readOneOf(
    params,
    PARAM.TRAINING,
    ONBOARDING_STATUSES,
  );
  const committedRoundId = roundIds.includes(urlRoundId)
    ? urlRoundId
    : defaultRoundId;
  const committedRole = params.get(PARAM.ROLE) ?? "";
  const committedApproval = params.get(PARAM.APPROVAL) ?? "";
  const isInProgress = (id) =>
    (rounds ?? []).some((r) => String(r.id) === id && r.isInProgress);
  const notRegisteredRequested = params.get(PARAM.NOT_REGISTERED) === "1";
  const notRegistered =
    notRegisteredRequested && isInProgress(committedRoundId);
  const eligibleRequested = params.get(PARAM.ELIGIBLE) === "1";
  const eligible =
    eligibleRequested &&
    !notRegisteredRequested &&
    isInProgress(committedRoundId);
  const sortBy = params.get(PARAM.SORT) || null;
  const order = sortBy && params.get(PARAM.ORDER) === "desc" ? "desc" : "asc";
  const offset = Number.parseInt(readDigits(params, PARAM.OFFSET) || "0", 10);

  // Rows remember which list they came from, so a switch between the
  // participants and Not registered never shows one list's rows under the
  // other's columns while the new list loads.
  const [listed, setListed] = useState({ notRegistered: false, rows: [] });
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const [userId, setUserId] = useState(committedUserId);
  const [q, setQ] = useState(committedQ);
  const [accountStatus, setAccountStatus] = useState(committedAccount);
  const [internal, setInternal] = useState(committedInternal);
  const [onboardingStatus, setOnboardingStatus] = useState(committedOnboarding);
  const [roundId, setDraftRoundId] = useState(committedRoundId);
  const [participantRole, setParticipantRole] = useState(committedRole);
  const [approvalStatus, setApprovalStatus] = useState(committedApproval);
  const [listNotRegistered, setListNotRegistered] = useState(notRegistered);
  const [listEligible, setListEligible] = useState(eligible);

  // Keep the inputs in step when the URL changes underneath them (back,
  // forward, or a pasted link).
  useEffect(() => setUserId(committedUserId), [committedUserId]);
  useEffect(() => setQ(committedQ), [committedQ]);
  useEffect(() => setAccountStatus(committedAccount), [committedAccount]);
  useEffect(() => setInternal(committedInternal), [committedInternal]);
  useEffect(
    () => setOnboardingStatus(committedOnboarding),
    [committedOnboarding],
  );
  useEffect(() => setDraftRoundId(committedRoundId), [committedRoundId]);
  useEffect(() => setParticipantRole(committedRole), [committedRole]);
  useEffect(() => setApprovalStatus(committedApproval), [committedApproval]);
  useEffect(() => setListNotRegistered(notRegistered), [notRegistered]);
  useEffect(() => setListEligible(eligible), [eligible]);

  // Write the resolved round back into a search whose round is unknown,
  // replacing the entry so back does not return to the unresolved link.
  useEffect(() => {
    if (!hasSearched || !committedRoundId) return;
    if (urlRoundId === committedRoundId) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set(PARAM.ROUND, committedRoundId);
        return next;
      },
      { replace: true },
    );
  }, [hasSearched, committedRoundId, urlRoundId, setSearchParams]);

  // Drop a Not registered request the round cannot honour, once the rounds
  // are known, so the URL says what the list shows.
  useEffect(() => {
    if (!hasSearched || rounds == null) return;
    if (!notRegisteredRequested || notRegistered) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete(PARAM.NOT_REGISTERED);
        return next;
      },
      { replace: true },
    );
  }, [
    hasSearched,
    rounds,
    notRegisteredRequested,
    notRegistered,
    setSearchParams,
  ]);

  // Likewise for an Eligible request, once the rounds are known.
  useEffect(() => {
    if (!hasSearched || rounds == null) return;
    if (!eligibleRequested || eligible) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete(PARAM.ELIGIBLE);
        return next;
      },
      { replace: true },
    );
  }, [hasSearched, rounds, eligibleRequested, eligible, setSearchParams]);

  const { begin, isCurrent } = useRequestGuard();

  const fetchRows = useCallback(
    async ({ silent = false } = {}) => {
      const seq = begin();
      if (!hasSearched || !canSearch) {
        setListed({ notRegistered, rows: [] });
        setTotal(0);
        setLoading(false);
        return;
      }
      if (!silent) setLoading(true);
      const person = {
        userId: committedUserId || undefined,
        q: committedQ || undefined,
        accountStatus: committedAccount || undefined,
        internal: committedInternal || undefined,
        limit: LIMIT,
        offset,
      };
      try {
        const { data } = notRegistered
          ? await searchUnregistered(committedRoundId, {
              ...person,
              admittedRole: committedRole || undefined,
              // Always by user ID; unsorted is that order ascending.
              order: sortBy ? order : "asc",
            })
          : await searchParticipants({
              ...person,
              onboardingStatus: committedOnboarding || undefined,
              eligible: eligible || undefined,
              sortBy: sortBy ?? undefined,
              order,
              roundId: committedRoundId,
              participantRole: committedRole || undefined,
              approvalStatus: committedApproval || undefined,
            });
        if (!isCurrent(seq)) return;
        setListed({
          notRegistered,
          rows: (notRegistered ? data.rows : data.participantRows) ?? [],
        });
        setTotal(data.total ?? 0);
      } catch (err) {
        if (!isCurrent(seq)) return;
        if (silent) return;
        toast.error(
          err?.response?.data?.message ?? "Failed to load participants",
        );
        setListed({ notRegistered, rows: [] });
        setTotal(0);
      } finally {
        if (!silent && isCurrent(seq)) setLoading(false);
      }
    },
    [
      hasSearched,
      canSearch,
      committedUserId,
      committedQ,
      committedAccount,
      committedInternal,
      committedOnboarding,
      committedRoundId,
      committedRole,
      committedApproval,
      eligible,
      notRegistered,
      offset,
      sortBy,
      order,
      begin,
      isCurrent,
    ],
  );

  useEffect(() => {
    fetchRows();
  }, [fetchRows]);

  /** Replace the query string with this search's state, dropping empties. */
  const writeUrl = (state) => {
    const next = new URLSearchParams();
    Object.entries(state).forEach(([key, value]) => {
      if (value !== "" && value !== null && value !== undefined) {
        next.set(key, String(value));
      }
    });
    setSearchParams(next);
    return next;
  };

  const withSort = (nextSortBy, nextOrder) => ({
    [PARAM.SORT]: nextSortBy,
    [PARAM.ORDER]: nextSortBy ? nextOrder : "",
  });

  /** Page or re-sort the committed search; draft inputs are not applied. */
  const navigate = ({
    nextOffset = offset,
    nextSortBy = sortBy,
    nextOrder = order,
  }) =>
    writeUrl({
      [PARAM.ID]: committedUserId,
      [PARAM.Q]: committedQ,
      [PARAM.ACCOUNT]: committedAccount,
      [PARAM.INTERNAL]: committedInternal,
      [PARAM.TRAINING]: committedOnboarding,
      [PARAM.ROUND]: committedRoundId,
      [PARAM.ROLE]: committedRole,
      [PARAM.APPROVAL]: committedApproval,
      ...withSort(nextSortBy, nextOrder),
      [PARAM.OFFSET]: nextOffset || "",
      [PARAM.NOT_REGISTERED]: notRegistered ? "1" : "",
      [PARAM.ELIGIBLE]: eligible ? "1" : "",
    });

  // Everything that picks who is listed, but not paging or sorting: a
  // selection made in one list stays valid only while this is unchanged.
  const listKey = hasSearched
    ? JSON.stringify([
        committedUserId,
        committedQ,
        committedAccount,
        committedInternal,
        committedOnboarding,
        committedRoundId,
        committedRole,
        committedApproval,
        notRegistered,
        eligible,
      ])
    : "";

  const draftRoundId = roundIds.includes(roundId) ? roundId : defaultRoundId;
  const canListNotRegistered = canSearch && isInProgress(draftRoundId);
  const canListEligible = canListNotRegistered;

  /** Pick the round; one not in progress goes back to Registered. */
  const setRoundId = (id) => {
    setDraftRoundId(id);
    if (!isInProgress(id)) {
      setListNotRegistered(false);
      setListEligible(false);
    }
  };

  /**
   * Turn Eligible for matching on or off. On is refused for a round not in
   * progress, and leaves Not registered.
   */
  const pickEligible = (on) => {
    if (on && !canListEligible) return;
    setListEligible(on);
    if (on) setListNotRegistered(false);
  };

  /**
   * Pick the list. Not registered is refused for a round not in progress;
   * picking it clears training and approval, which it has neither of.
   */
  const pickNotRegistered = (on) => {
    if (on && !canListNotRegistered) return;
    setListNotRegistered(on);
    if (on) {
      setOnboardingStatus("");
      setApprovalStatus("");
      setListEligible(false);
    }
  };

  /** Commit the drafts as the search and load its first page. */
  const submitSearch = () => {
    if (!canSearch) return;
    const inNotRegistered = listNotRegistered && canListNotRegistered;
    const inEligible = listEligible && canListEligible && !inNotRegistered;
    const before = searchParams.toString();
    const after = writeUrl({
      [PARAM.ID]: userId,
      [PARAM.Q]: q.trim(),
      [PARAM.ACCOUNT]: accountStatus,
      [PARAM.INTERNAL]: internal,
      [PARAM.TRAINING]: inNotRegistered ? "" : onboardingStatus,
      [PARAM.ROUND]: draftRoundId,
      [PARAM.ROLE]: participantRole,
      [PARAM.APPROVAL]: inNotRegistered ? "" : approvalStatus,
      ...withSort(sortBy, order),
      [PARAM.NOT_REGISTERED]: inNotRegistered ? "1" : "",
      [PARAM.ELIGIBLE]: inEligible ? "1" : "",
    }).toString();
    // Searching again for what is already committed still re-reads the list.
    if (before === after) fetchRows();
  };

  const nextPage = () => {
    if (offset + LIMIT < total) navigate({ nextOffset: offset + LIMIT });
  };
  const prevPage = () => navigate({ nextOffset: Math.max(0, offset - LIMIT) });

  /**
   * Toggle sort through a three-state cycle: asc -> desc -> unsorted (back to
   * the default order) -> asc. The unsorted step leaves a way back to the
   * default order, which sorts by name. Returns to the first page.
   * @param {string} field - Backend sort_by field name (e.g. "user_id").
   */
  const toggleSort = (field) => {
    if (sortBy !== field) {
      navigate({ nextOffset: 0, nextSortBy: field, nextOrder: "asc" });
    } else if (order === "asc") {
      navigate({ nextOffset: 0, nextSortBy: field, nextOrder: "desc" });
    } else {
      navigate({ nextOffset: 0, nextSortBy: null, nextOrder: "asc" });
    }
  };

  return {
    rows: listed.notRegistered === notRegistered ? listed.rows : [],
    total,
    loading,
    hasSearched,
    canSearch,
    refetch: () => fetchRows({ silent: true }),
    userId,
    setUserId,
    q,
    setQ,
    accountStatus,
    setAccountStatus,
    internal,
    setInternal,
    roundId,
    setRoundId,
    participantRole,
    setParticipantRole,
    approvalStatus,
    setApprovalStatus,
    onboardingStatus,
    setOnboardingStatus,
    submitSearch,
    committedRoundId,
    listKey,
    notRegistered,
    listNotRegistered,
    setListNotRegistered: pickNotRegistered,
    canListNotRegistered,
    eligible,
    listEligible,
    setListEligible: pickEligible,
    canListEligible,
    offset,
    limit: LIMIT,
    nextPage,
    prevPage,
    sortBy,
    order,
    toggleSort,
  };
};
