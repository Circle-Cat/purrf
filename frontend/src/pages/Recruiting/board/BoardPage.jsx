import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import LoadGate from "@/pages/Recruiting/components/LoadGate";
import ApplicantCard from "@/pages/Recruiting/board/ApplicantCard";
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
import HowItWorksDialog from "@/pages/Recruiting/components/HowItWorksDialog";
import { APPLICATIONS_BOARD_GUIDE } from "@/pages/Recruiting/components/guideContent";

/** Offer is always inserted between an employment job's configured pipeline
 * stages and the terminal lanes — never something a job opts into (see
 * TERMINAL_STAGES, the same treatment). Activity jobs have no offer step at
 * all: their last configured stage advances straight to hired ("Admitted"). */
const OFFER_STAGE = "offer";
/** Terminal lanes always appended after a job's configured pipeline stages. */
const TERMINAL_STAGES = ["hired", "rejected"];

/**
 * Owner-facing kanban board: pick a job you own from the switcher, see its
 * applicants laid out in lanes by pipeline stage, with the two terminal
 * lanes (Hired — labeled Admitted for activity jobs — and Rejected) always
 * shown at the end.
 */
const BoardPage = () => {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [board, setBoard] = useState(null);
  const [boardError, setBoardError] = useState(false);
  /** Stages with an in-flight "Load more" fetch, so a fast double-click on
   * the same lane can't fire a second request against a stale offset. */
  const [loadingMore, setLoadingMore] = useState(() => new Set());

  /** Fetch (or re-fetch, via Retry) the caller's owned jobs. */
  const loadJobs = useCallback(async () => {
    setLoadError(false);
    setJobs(null);
    try {
      const { data } = await listBoardJobs();
      setJobs(data ?? []);
      if (data?.length > 0) {
        setSelectedJobId(data[0].id);
      }
    } catch (e) {
      setLoadError(true);
      toast.error(e.message);
    }
  }, []);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  /** Fetch (or re-fetch, via Retry) the selected job's board, grouped by stage. */
  const loadBoard = useCallback(async (jobId) => {
    setBoardError(false);
    setBoard(null);
    try {
      const { data } = await getJobBoard(jobId);
      setBoard(data?.stages ?? {});
    } catch (e) {
      setBoardError(true);
      toast.error(e.message);
    }
  }, []);

  useEffect(() => {
    if (selectedJobId != null) {
      loadBoard(selectedJobId);
    }
  }, [selectedJobId, loadBoard]);

  /** Fetch the next page of a terminal lane (hired/rejected) and append it,
   * deduping by card id so a slow double-click can't render duplicates. */
  const loadMore = useCallback(
    async (stage) => {
      if (loadingMore.has(stage)) return;
      setLoadingMore((prev) => new Set(prev).add(stage));
      const lane = board[stage];
      try {
        const { data } = await getJobBoardStagePage(selectedJobId, {
          stage,
          limit: 20,
          offset: lane.items.length,
        });
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
        toast.error(e.message);
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
            label: `${humanize(stage)} — Round ${i + 1}`,
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
            value={String(selectedJobId)}
            onValueChange={(value) => setSelectedJobId(Number(value))}
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
        </div>
        <HowItWorksDialog {...APPLICATIONS_BOARD_GUIDE} />
      </div>

      {!board ? (
        <LoadGate
          error={boardError}
          errorMessage="Couldn't load the board."
          onRetry={() => loadBoard(selectedJobId)}
        />
      ) : (
        <div className="flex flex-1 gap-4 overflow-x-auto pb-4">
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
                    {isTerminal ? (board[lane.stage]?.total ?? cards.length) : cards.length}
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
      )}
    </div>
  );
};

export default BoardPage;
