import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import TermHint from "@/pages/Recruiting/components/TermHint";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import LoadGate from "@/pages/Recruiting/components/LoadGate";
import ApplicantCard from "@/pages/Recruiting/board/ApplicantCard";
import ApplicantSearch from "@/pages/Recruiting/board/ApplicantSearch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  listBoardJobs,
  getJobBoard,
  getJobBoardStagePage,
} from "@/api/recruitingApi";
import { humanize, stageLabel } from "@/pages/Recruiting/board/stageFormat";
import { getStageColors } from "@/pages/Recruiting/board/stageColors";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/** Offer is always inserted between an employment job's configured pipeline
 * stages and the terminal lanes — never something a job opts into (see
 * TERMINAL_STAGES, the same treatment). Activity jobs have no offer step at
 * all: their last configured stage advances straight to hired ("Admitted"). */
const OFFER_STAGE = "offer";
/** Terminal lanes always appended after a job's configured pipeline stages. */
const TERMINAL_STAGES = ["hired", "rejected"];
/** Rounds of terminal-lane paging spent hunting for a `?focus=` card before
 * giving up. Bounded because a rejected lane can be arbitrarily long, and
 * relocating a card is a convenience, not a guarantee. */
const FOCUS_PAGE_LIMIT = 5;
/** How long the relocated card keeps its ring. */
const FOCUS_HIGHLIGHT_MS = 3000;

/**
 * Owner-facing kanban board: pick a job you own from the switcher, see its
 * applicants laid out in lanes by pipeline stage, with the two terminal
 * lanes (Hired — labeled Admitted for activity jobs — and Rejected) always
 * shown at the end.
 *
 * Both the selected job and an optional post-decision relocation target ride
 * in the URL (`?jobId=`, `?focus=`), so returning from an applicant's detail
 * page restores the job and lands on that applicant's card.
 */
const BoardPage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  // The selected job lives in the URL, not in state: the board is navigated
  // away from and back to constantly (open an applicant, act, return), and
  // component state resets to the first job every time that happens. One
  // source of truth also makes the board's URL shareable.
  const selectedJobId = Number(searchParams.get("jobId")) || null;
  const focusId = Number(searchParams.get("focus")) || null;
  const [jobs, setJobs] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [board, setBoard] = useState(null);
  const [boardError, setBoardError] = useState(false);
  /** Stages with an in-flight "Load more" fetch, so a fast double-click on
   * the same lane can't fire a second request against a stale offset. */
  const [loadingMore, setLoadingMore] = useState(() => new Set());
  /** The card wearing the relocation ring, if any. */
  const [highlightedId, setHighlightedId] = useState(null);
  /** Wraps the lane list so the focus hunt's card lookup can be scoped to
   * it — `ApplicantSearch`'s result rows carry the same `data-application-id`
   * attribute and sit earlier in the DOM, so a document-wide query can match
   * a dropdown row instead of the card. */
  const lanesRef = useRef(null);
  /** Rounds of paging already spent on the current board's focus hunt. */
  const focusRounds = useRef(0);
  /** Terminal lanes whose paging failed during a focus hunt. A failed page
   * leaves `has_more` true and the offset unchanged, so without this the hunt
   * would re-issue the identical request every remaining round. */
  const focusPageFailures = useRef(new Set());

  /** Fetch (or re-fetch, via Retry) the caller's owned jobs. */
  const loadJobs = useCallback(async () => {
    setLoadError(false);
    setJobs(null);
    try {
      const { data } = await listBoardJobs();
      setJobs(data ?? []);
    } catch (e) {
      setLoadError(true);
      toast.error(e.message);
    }
  }, []);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  /** Keep `?jobId=` pointing at a job the caller actually owns. An absent,
   * unparseable, or no-longer-owned id falls back to the first job — the
   * behaviour before the param existed — rewritten in place so the URL never
   * disagrees with what's on screen. `replace` keeps the correction out of
   * the history stack. */
  useEffect(() => {
    if (!jobs?.length) return;
    if (jobs.some((job) => job.id === selectedJobId)) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("jobId", String(jobs[0].id));
        // A focus id is only meaningful against the job it was minted for.
        next.delete("focus");
        return next;
      },
      { replace: true },
    );
  }, [jobs, selectedJobId, setSearchParams]);

  /** Drop `?focus=` in place, so neither a refresh nor an unrelated re-render
   * repeats a relocation that has already happened (or already failed). */
  const clearFocusParam = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("focus");
        return next;
      },
      { replace: true },
    );
  }, [setSearchParams]);

  /** Fetch (or re-fetch, via Retry) the selected job's board, grouped by stage. */
  const loadBoard = useCallback(async (jobId) => {
    setBoardError(false);
    setBoard(null);
    focusRounds.current = 0;
    focusPageFailures.current.clear();
    try {
      const { data } = await getJobBoard(jobId);
      setBoard(data?.stages ?? {});
    } catch (e) {
      setBoardError(true);
      toast.error(e.message);
    }
  }, []);

  // Wait for the owned-jobs list before fetching a board. `selectedJobId` is
  // readable from the URL on the first render, when `jobs` is still null, so
  // an unguarded fetch would fire against a job the caller may not own — and
  // `loadBoard` surfaces that rejection as an error toast. Gating here also
  // restores the pre-URL ordering, where selection could only happen after
  // the list had loaded.
  useEffect(() => {
    if (
      selectedJobId != null &&
      jobs?.some((job) => job.id === selectedJobId)
    ) {
      loadBoard(selectedJobId);
    }
  }, [selectedJobId, jobs, loadBoard]);

  /** Fetch the next page of a terminal lane (hired/rejected) and append it,
   * deduping by card id so a slow double-click can't render duplicates. */
  const loadMore = useCallback(
    async (stage, { silent = false } = {}) => {
      if (loadingMore.has(stage)) return;
      setLoadingMore((prev) => new Set(prev).add(stage));
      const lane = board[stage];
      try {
        const { data } = await getJobBoardStagePage(selectedJobId, {
          stage,
          limit: 20,
          offset: lane.items.length,
        });
        if (silent) focusPageFailures.current.delete(stage);
        setBoard((prev) => {
          const seen = new Set(prev[stage].items.map((c) => c.id));
          const merged = [
            ...prev[stage].items,
            ...data.items.filter((c) => !seen.has(c.id)),
          ];
          return {
            ...prev,
            [stage]: { ...prev[stage], items: merged, has_more: data.has_more },
          };
        });
      } catch (e) {
        // A background focus hunt stays quiet on failure: relocating a card
        // is a convenience the owner didn't ask for, so its failure is as
        // silent as not finding the card at all.
        if (silent) {
          focusPageFailures.current.add(stage);
        } else {
          toast.error(e.message);
        }
      } finally {
        setLoadingMore((prev) => {
          const next = new Set(prev);
          next.delete(stage);
          return next;
        });
      }
    },
    [board, selectedJobId, loadingMore],
  );

  /** Bring the `?focus=` applicant to the owner: scroll their card into view
   * and ring it, so returning from a decision lands on the person just dealt
   * with instead of the far left of the board.
   *
   * The card is found by DOM attribute rather than by a ref, because cards
   * are rendered by a `map` inside each lane and threading refs back out
   * would couple the two components for nothing. The lookup is scoped to the
   * lanes container, not `document`: `ApplicantSearch`'s result rows carry
   * this same `data-application-id` attribute (deliberately shared) and sit
   * earlier in the DOM, so a document-wide query can match a search result
   * row instead of the card while both are on screen.
   *
   * A just-rejected applicant can sit past a terminal lane's first page (that
   * lane orders by `stage_entered_at DESC` with no NULLS LAST, and the column
   * was never backfilled, so un-timed rows crowd the top), hence the bounded
   * paging hunt. Failure is silent: the job is already selected, which is the
   * bulk of the value. */
  useEffect(() => {
    if (focusId == null || !board) return;

    const el = lanesRef.current?.querySelector(
      `[data-application-id="${focusId}"]`,
    );
    if (el) {
      el.scrollIntoView({ block: "nearest", inline: "center" });
      setHighlightedId(focusId);
      clearFocusParam();
      return;
    }

    // A page is on its way; re-run when it lands rather than deciding now.
    if (TERMINAL_STAGES.some((stage) => loadingMore.has(stage))) return;

    const pageable = TERMINAL_STAGES.filter(
      (stage) =>
        board[stage]?.has_more && !focusPageFailures.current.has(stage),
    );
    if (pageable.length === 0 || focusRounds.current >= FOCUS_PAGE_LIMIT) {
      clearFocusParam();
      return;
    }
    focusRounds.current += 1;
    pageable.forEach((stage) => loadMore(stage, { silent: true }));
  }, [focusId, board, loadingMore, loadMore, clearFocusParam]);

  /** Retire the ring on its own timer, decoupled from the URL param (which
   * is cleared as soon as the card is found, so a refresh can't replay it). */
  useEffect(() => {
    if (highlightedId == null) return;
    const timer = setTimeout(() => setHighlightedId(null), FOCUS_HIGHLIGHT_MS);
    return () => clearTimeout(timer);
  }, [highlightedId]);

  const selectedJob = useMemo(
    () => jobs?.find((job) => job.id === selectedJobId) ?? null,
    [jobs, selectedJobId],
  );

  const lanes = useMemo(() => {
    if (!selectedJob) return [];
    const pipelineLanes = selectedJob.stages.flatMap(({ stage, rounds }) =>
      rounds > 1
        ? Array.from({ length: rounds }, (_, i) => ({
            key: `${stage}:${i + 1}`,
            stage,
            round: i + 1,
            isLastRound: i + 1 === rounds,
            label: `${humanize(stage)} — Session ${i + 1}`,
          }))
        : [
            {
              key: stage,
              stage,
              round: null,
              isLastRound: false,
              label: humanize(stage),
            },
          ],
    );
    const offerLanes =
      selectedJob.kind === "activity"
        ? []
        : [
            {
              key: OFFER_STAGE,
              stage: OFFER_STAGE,
              round: null,
              label: humanize(OFFER_STAGE),
            },
          ];
    const terminalLanes = TERMINAL_STAGES.map((stage) => ({
      key: stage,
      stage,
      round: null,
      label: stageLabel(stage, selectedJob.kind),
    }));
    return [...pipelineLanes, ...offerLanes, ...terminalLanes];
  }, [selectedJob]);

  /** Navigate to the shared application detail page for the clicked card. */
  const handleOpen = useCallback(
    (applicationId) => {
      navigate(ROUTE_PATHS.RECRUITING_APPLICATION_DETAIL(applicationId));
    },
    [navigate],
  );

  if (!jobs) {
    return (
      <LoadGate
        error={loadError}
        errorMessage="Couldn't load your postings."
        onRetry={loadJobs}
      />
    );
  }

  if (jobs.length === 0) {
    return (
      <p className="p-6 text-sm text-muted-foreground">
        You don&apos;t own any postings.
      </p>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-900">
            Applications Board
          </h1>
          <Select
            value={selectedJobId == null ? undefined : String(selectedJobId)}
            onValueChange={(value) =>
              setSearchParams(
                (prev) => {
                  const next = new URLSearchParams(prev);
                  next.set("jobId", value);
                  // Switching jobs by hand abandons any pending relocation.
                  next.delete("focus");
                  return next;
                },
                // Switching jobs inside the board isn't a navigation step:
                // browser-back should leave the board, not replay selections.
                { replace: true },
              )
            }
          >
            <SelectTrigger aria-label="Job" className="w-64">
              <SelectValue placeholder="Select a job…" />
            </SelectTrigger>
            <SelectContent>
              {jobs.map((job) => (
                <SelectItem key={job.id} value={String(job.id)}>
                  {job.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <ApplicantSearch
            selectedJobId={selectedJobId}
            onSelect={handleOpen}
          />
        </div>
      </div>

      {!board ? (
        <LoadGate
          error={boardError}
          errorMessage="Couldn't load the board."
          onRetry={() => loadBoard(selectedJobId)}
        />
      ) : (
        <>
          <p className="text-xs text-slate-500">
            <TermHint id="board.lanes" />
          </p>
          <div
            ref={lanesRef}
            className="flex flex-1 gap-4 overflow-x-auto pb-4"
          >
            {lanes.map((lane) => {
              const cardsForStage = board[lane.stage]?.items ?? [];
              // A stage's configured rounds can shrink after applicants are
              // already staged past the new max (e.g. an owner edits "tech"
              // from 3 rounds down to 2); the last round lane catches those
              // stale higher rounds instead of silently hiding the applicant.
              const cards =
                lane.round == null
                  ? cardsForStage
                  : cardsForStage.filter((c) =>
                      lane.isLastRound
                        ? c.round >= lane.round
                        : c.round === lane.round,
                    );
              const isTerminal = TERMINAL_STAGES.includes(lane.stage);
              const colors = getStageColors(lane.stage);
              return (
                <div
                  key={lane.key}
                  data-testid={`lane-${lane.key}`}
                  className={`flex w-72 shrink-0 flex-col rounded-lg border ${colors.border} ${colors.tint}`}
                >
                  <div
                    className={`flex items-center justify-between rounded-t-lg border-b px-3 py-2 ${colors.header} ${colors.border}`}
                  >
                    <h2 className="text-sm font-semibold">{lane.label}</h2>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${colors.count}`}
                    >
                      {isTerminal
                        ? (board[lane.stage]?.total ?? cards.length)
                        : cards.length}
                    </span>
                  </div>
                  <div className="flex flex-col gap-2 p-3">
                    {cards.length === 0 ? (
                      <p className="text-xs text-muted-foreground">
                        No applicants
                      </p>
                    ) : (
                      cards.map((card) => (
                        <ApplicantCard
                          key={card.id}
                          card={card}
                          showStatus={!isTerminal}
                          highlighted={card.id === highlightedId}
                          onOpen={handleOpen}
                        />
                      ))
                    )}
                    {isTerminal && board[lane.stage]?.has_more && (
                      <button
                        type="button"
                        onClick={() => loadMore(lane.stage)}
                        disabled={loadingMore.has(lane.stage)}
                        className="mt-1 rounded-md border border-border px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Load more
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};

export default BoardPage;
