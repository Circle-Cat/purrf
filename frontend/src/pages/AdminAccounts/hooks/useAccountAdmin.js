import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import {
  blockAccount,
  deactivateAccount,
  decideBlockRequest,
  getAccounts,
  getBlockPreflight,
  getPendingBlockRequests,
  getSignInMethods,
  reactivateAccount,
  unblockAccount,
} from "@/api/adminAccountsApi";
import { useRequestGuard } from "@/hooks/useRequestGuard";

const LIMIT = 20;

/**
 * Query-string keys. Unlike the permission page, this console keeps its search,
 * filters and page in the URL: `?status=blocked` has to be a shareable deep
 * link, and coming back from one person's detail has to land on the same list
 * rather than a reset one.
 *
 * `user_id` opens the detail view; `focus` only rings the row the viewer came
 * back from, so returning never collapses the list to a single person.
 */
export const PARAM = Object.freeze({
  SEARCH: "search",
  USER_TYPE: "user_type",
  STATUS: "status",
  OFFSET: "offset",
  PENDING: "pending",
  FOCUS: "focus",
  USER_ID: "user_id",
});

/** Read an integer query parameter, falling back when it is absent or junk. */
const readInt = (params, key, fallback) => {
  const raw = params.get(key);
  if (raw === null) return fallback;
  const value = Number.parseInt(raw, 10);
  return Number.isNaN(value) ? fallback : value;
};

/**
 * Owns the account console list: the committed search, the Type/Status
 * filters, the page, and the caller's own pending block requests. Every one of
 * those lives in the query string, so the hook holds only the draft search box
 * and the fetched rows.
 */
export const useAccountAdmin = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  const search = searchParams.get(PARAM.SEARCH) ?? "";
  const userType = searchParams.get(PARAM.USER_TYPE) ?? "";
  const status = searchParams.get(PARAM.STATUS) ?? "";
  const offset = Math.max(0, readInt(searchParams, PARAM.OFFSET, 0));
  const pendingOnly = searchParams.get(PARAM.PENDING) === "1";
  const focusedUserId = searchParams.has(PARAM.FOCUS)
    ? readInt(searchParams, PARAM.FOCUS, null)
    : null;

  // The search box is a draft until Enter or the Search button commits it to
  // the URL; the two selects commit immediately.
  const [searchDraft, setSearchDraft] = useState(search);
  const [accounts, setAccounts] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [pendingRequests, setPendingRequests] = useState([]);

  const { begin, isCurrent } = useRequestGuard();

  /**
   * Merge into the query string, dropping empties. Any change other than the
   * page itself returns to the first page, and clears the returned-from
   * highlight, which only makes sense for the list it was captured on.
   */
  const updateParams = useCallback(
    (changes, { resetPage = true } = {}) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          Object.entries(changes).forEach(([key, value]) => {
            if (value === "" || value === null || value === undefined) {
              next.delete(key);
            } else {
              next.set(key, String(value));
            }
          });
          if (resetPage && !(PARAM.OFFSET in changes)) {
            next.delete(PARAM.OFFSET);
            next.delete(PARAM.FOCUS);
          }
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );

  // A stable dependency for the pending-only view. Empty whenever that view is
  // off, so the list does not refetch when the banner's own read lands.
  const pendingKey = useMemo(
    () =>
      pendingOnly ? pendingRequests.map((r) => r.targetUserId).join(",") : "",
    [pendingOnly, pendingRequests],
  );

  const fetchAccounts = useCallback(async () => {
    const seq = begin();
    setLoading(true);
    try {
      if (pendingOnly) {
        // The list endpoint has no "requests waiting on me" filter -- the
        // requests are the caller's own, not a property of the population. The
        // ids come from the pending list and are fetched one by one, which is
        // fine: a reviewer has a handful of these, never a page of them.
        const targetIds = pendingKey ? pendingKey.split(",").map(Number) : [];
        const responses = await Promise.all(
          targetIds.map((id) => getAccounts({ userId: id, limit: 1 })),
        );
        if (!isCurrent(seq)) return;
        const rows = responses.flatMap((r) => r?.data?.accounts ?? []);
        setAccounts(rows);
        setTotal(rows.length);
        return;
      }
      const { data } = await getAccounts({
        search: search || undefined,
        status: status || undefined,
        userType: userType || undefined,
        limit: LIMIT,
        offset,
      });
      if (!isCurrent(seq)) return;
      setAccounts(data?.accounts ?? []);
      setTotal(data?.total ?? 0);
    } catch (err) {
      if (!isCurrent(seq)) return;
      toast.error(err?.response?.data?.message ?? "Failed to load accounts");
      setAccounts([]);
      setTotal(0);
    } finally {
      if (isCurrent(seq)) setLoading(false);
    }
  }, [
    search,
    status,
    userType,
    offset,
    pendingOnly,
    pendingKey,
    begin,
    isCurrent,
  ]);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  const loadPendingRequests = useCallback(async () => {
    try {
      const { data } = await getPendingBlockRequests();
      setPendingRequests(data ?? []);
    } catch {
      // A failed banner must not take the list down with it: the console is
      // still usable without knowing the caller's own request count.
      setPendingRequests([]);
    }
  }, []);

  useEffect(() => {
    loadPendingRequests();
  }, [loadPendingRequests]);

  // Keep the box in step when the URL changes underneath it (deep link, back
  // button, or returning from a detail page).
  useEffect(() => {
    setSearchDraft(search);
  }, [search]);

  const submitSearch = () => updateParams({ [PARAM.SEARCH]: searchDraft });
  const setUserType = (value) => updateParams({ [PARAM.USER_TYPE]: value });
  const setStatus = (value) => updateParams({ [PARAM.STATUS]: value });
  // The search and filters are kept, not cleared: pending-only ignores them
  // while it is on (the list is a fixed set of ids, not a query), and keeping
  // them is what lets "Show all accounts" put the reviewer back where they
  // were. AccountList disables the controls so the pause is visible.
  const showPendingOnly = () => updateParams({ [PARAM.PENDING]: "1" });
  const clearPendingOnly = () => updateParams({ [PARAM.PENDING]: "" });

  const nextPage = () => {
    if (offset + LIMIT < total)
      updateParams({ [PARAM.OFFSET]: offset + LIMIT }, { resetPage: false });
  };
  const prevPage = () =>
    updateParams(
      { [PARAM.OFFSET]: Math.max(0, offset - LIMIT) || "" },
      { resetPage: false },
    );

  /** Open one account, leaving the list's own parameters in the URL. */
  const openAccount = (account) =>
    updateParams(
      { [PARAM.USER_ID]: account.userId, [PARAM.FOCUS]: "" },
      { resetPage: false },
    );

  return {
    accounts,
    total,
    loading,
    search: searchDraft,
    setSearch: setSearchDraft,
    submitSearch,
    userType,
    setUserType,
    status,
    setStatus,
    offset,
    limit: LIMIT,
    nextPage,
    prevPage,
    openAccount,
    focusedUserId,
    pendingRequests,
    pendingCount: pendingRequests.length,
    pendingOnly,
    showPendingOnly,
    clearPendingOnly,
  };
};

/**
 * Owns one account's detail view: the row itself, its sign-in methods, the
 * block request waiting on the caller (if any), the block pre-flight, and
 * every state-changing action on the page.
 *
 * @param {number|null} userId - The account being viewed.
 */
export const useAccountDetail = (userId) => {
  const [account, setAccount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [signInMethods, setSignInMethods] = useState(null);
  const [pendingRequest, setPendingRequest] = useState(null);
  // These two reads are allowed to fail without taking the page down, so the
  // page has to be able to tell "read it, there is none" from "could not read
  // it". Rendering the first when the second is true states a fact about the
  // person that nobody established.
  const [signInMethodsFailed, setSignInMethodsFailed] = useState(false);
  const [pendingRequestFailed, setPendingRequestFailed] = useState(false);
  const [preflight, setPreflight] = useState(null);
  const [preflightError, setPreflightError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const { begin, isCurrent } = useRequestGuard();

  const load = useCallback(async () => {
    if (!userId) return;
    const seq = begin();
    setLoading(true);
    try {
      // Only the account read decides whether this page has anything to show.
      // The other two are decoration on it, and a failure in either used to
      // make the page announce that an account that plainly exists does not.
      const [listed, methods, pending] = await Promise.allSettled([
        getAccounts({ userId, limit: 1 }),
        getSignInMethods(userId),
        getPendingBlockRequests(),
      ]);
      if (!isCurrent(seq)) return;

      if (listed.status === "rejected") {
        toast.error(
          listed.reason?.response?.data?.message ??
            "Failed to load the account",
        );
        setAccount(null);
        setNotFound(true);
        return;
      }
      const row = listed.value?.data?.accounts?.[0] ?? null;
      setAccount(row);
      // An id nobody holds is an empty result, not an error. Saying so once,
      // in the page, beats saying it twice in two different voices.
      setNotFound(row === null);

      setSignInMethods(
        methods.status === "fulfilled" ? (methods.value?.data ?? null) : null,
      );
      setSignInMethodsFailed(methods.status === "rejected");
      // A request is only ever shown to the reviewer it names -- this endpoint
      // already returns nobody else's, so a match here is the caller's to
      // decide.
      const pendingRows =
        pending.status === "fulfilled" ? (pending.value?.data ?? []) : [];
      setPendingRequest(
        pendingRows.find((r) => r.targetUserId === userId) ?? null,
      );
      setPendingRequestFailed(pending.status === "rejected");
    } catch (err) {
      if (!isCurrent(seq)) return;
      toast.error(err?.response?.data?.message ?? "Failed to load the account");
      setNotFound(true);
    } finally {
      if (isCurrent(seq)) setLoading(false);
    }
  }, [userId, begin, isCurrent]);

  useEffect(() => {
    load();
  }, [load]);

  /** Run one state change, then re-read the account it changed. */
  const runAction = async (fn, successMessage, failureMessage) => {
    setSubmitting(true);
    try {
      await fn();
      toast.success(successMessage);
      await load();
      return true;
    } catch (err) {
      toast.error(err?.response?.data?.message ?? failureMessage);
      // Re-read on failure too. A refusal is often the server telling us the
      // row moved under us -- a request someone else decided, an account
      // already blocked -- and leaving the old view up invites the same click.
      await load();
      return false;
    } finally {
      setSubmitting(false);
    }
  };

  const deactivate = (note) =>
    runAction(
      () => deactivateAccount(userId, note),
      "Account deactivated.",
      "Failed to deactivate the account",
    );

  const reactivate = () =>
    runAction(
      () => reactivateAccount(userId),
      "Account reactivated.",
      "Failed to reactivate the account",
    );

  const unblock = () =>
    runAction(
      () => unblockAccount(userId),
      "Account unblocked.",
      "Failed to unblock the account",
    );

  const block = ({ reason }) =>
    runAction(
      () => blockAccount(userId, reason),
      "Account blocked.",
      "Failed to block the account",
    );

  const decideRequest = (approved, note) =>
    runAction(
      () => decideBlockRequest(pendingRequest.id, approved, note),
      approved ? "Request approved." : "Request rejected.",
      "Failed to record the decision",
    );

  /** Read what a block is about to do. Called when the dialog opens. */
  const loadPreflight = useCallback(async () => {
    setPreflight(null);
    setPreflightError(null);
    try {
      const { data } = await getBlockPreflight(userId);
      setPreflight(data ?? null);
    } catch (err) {
      setPreflightError(
        err?.response?.data?.message ?? "Failed to load the pre-flight check",
      );
    }
  }, [userId]);

  return {
    account,
    loading,
    notFound,
    signInMethods,
    signInMethodsFailed,
    pendingRequest,
    pendingRequestFailed,
    preflight,
    preflightError,
    loadPreflight,
    submitting,
    deactivate,
    reactivate,
    unblock,
    block,
    decideRequest,
  };
};
