import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { searchParticipants } from "@/api/mentorshipApi";
import { useRequestGuard } from "@/hooks/useRequestGuard";

const LIMIT = 20;

/**
 * Owns both the Participant and Non-participant tab searches, switched by
 * `participationStatus`. Search inputs are staged as draft state and only
 * take effect when submitSearch() runs (the Search button) — nothing is
 * fetched on mount. Participants additionally get round-scoped filters
 * (matched partner, round, role, approval status); user ID, name, email, and
 * onboarding status apply to both tabs since they don't depend on round data.
 */
export const useParticipantSearch = (participationStatus) => {
  const isParticipant = participationStatus === "participant";

  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  // Draft search inputs — applied only when submitSearch() runs.
  const [userId, setUserId] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [matchedUser, setMatchedUser] = useState("");
  const [roundId, setRoundId] = useState("");
  const [participantRole, setParticipantRole] = useState("");
  const [approvalStatus, setApprovalStatus] = useState("");
  const [onboardingStatus, setOnboardingStatus] = useState("");

  // Committed query: null until the user runs a search.
  const [query, setQuery] = useState(null);
  const [offset, setOffset] = useState(0);

  // Sort state (applies to the committed query).
  const [sortBy, setSortBy] = useState(null);
  const [order, setOrder] = useState("asc");
  const { begin, isCurrent } = useRequestGuard();

  const fetchRows = useCallback(async () => {
    if (!query) return;
    const seq = begin();
    setLoading(true);
    try {
      const { data } = await searchParticipants({
        userId: query.userId || undefined,
        name: query.name || undefined,
        email: query.email || undefined,
        onboardingStatus: query.onboardingStatus || undefined,
        participationStatus,
        limit: LIMIT,
        offset,
        sortBy: sortBy ?? undefined,
        order,
        ...(isParticipant && {
          matchedUser: query.matchedUser || undefined,
          roundId: query.roundId || undefined,
          participantRole: query.participantRole || undefined,
          approvalStatus: query.approvalStatus || undefined,
        }),
      });
      if (!isCurrent(seq)) return;
      setRows(data.participantRows ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      if (!isCurrent(seq)) return;
      toast.error(
        err?.response?.data?.message ??
          (isParticipant
            ? "Failed to load participants"
            : "Failed to load non-participants"),
      );
      setRows([]);
      setTotal(0);
    } finally {
      if (isCurrent(seq)) setLoading(false);
    }
  }, [
    query,
    offset,
    sortBy,
    order,
    begin,
    isCurrent,
    participationStatus,
    isParticipant,
  ]);

  useEffect(() => {
    fetchRows();
  }, [fetchRows]);

  /** Commit the current draft inputs as the active query and load page 1. */
  const submitSearch = () => {
    setOffset(0);
    setQuery({
      userId,
      name,
      email,
      onboardingStatus,
      ...(isParticipant && {
        matchedUser,
        roundId,
        participantRole,
        approvalStatus,
      }),
    });
  };

  const nextPage = () => {
    if (offset + LIMIT < total) setOffset((o) => o + LIMIT);
  };
  const prevPage = () => setOffset((o) => Math.max(0, o - LIMIT));

  /**
   * Toggle sort through a three-state cycle: asc -> desc -> unsorted (back to
   * the default order) -> asc. Unlike a plain asc/desc toggle, this always
   * leaves a way back to the default order, which sorts by name rather than
   * by the sort fields exposed here. Resets to the first page.
   * @param {string} field - Backend sort_by field name (e.g. "user_id").
   */
  const toggleSort = (field) => {
    setOffset(0);
    if (sortBy !== field) {
      setSortBy(field);
      setOrder("asc");
      return;
    }
    if (order === "asc") {
      setOrder("desc");
      return;
    }
    setSortBy(null);
    setOrder("asc");
  };

  return {
    rows,
    total,
    loading,
    hasSearched: query !== null,
    userId,
    setUserId,
    name,
    setName,
    email,
    setEmail,
    matchedUser,
    setMatchedUser,
    roundId,
    setRoundId,
    participantRole,
    setParticipantRole,
    approvalStatus,
    setApprovalStatus,
    onboardingStatus,
    setOnboardingStatus,
    submitSearch,
    offset,
    limit: LIMIT,
    nextPage,
    prevPage,
    sortBy,
    order,
    toggleSort,
  };
};
