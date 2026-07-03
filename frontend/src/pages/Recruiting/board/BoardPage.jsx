import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import LoadGate from "@/pages/Recruiting/components/LoadGate";
import ApplicantCard from "@/pages/Recruiting/board/ApplicantCard";
import ApplicantDetailDialog from "@/pages/Recruiting/board/ApplicantDetailDialog";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { listBoardJobs, getJobBoard } from "@/api/recruitingApi";
import { humanize } from "@/pages/Recruiting/board/stageFormat";

/** Terminal lanes always appended after a job's configured pipeline stages. */
const TERMINAL_STAGES = ["hired", "rejected"];

/**
 * Owner-facing kanban board: pick a job you own from the switcher, see its
 * applicants laid out in lanes by pipeline stage, with the two terminal
 * lanes (Hired, Rejected) always shown at the end.
 */
const BoardPage = () => {
  const [jobs, setJobs] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [board, setBoard] = useState(null);
  const [boardError, setBoardError] = useState(false);
  const [selectedApplicationId, setSelectedApplicationId] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);

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
      setBoard(data ?? {});
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
    const terminalLanes = TERMINAL_STAGES.map((stage) => ({
      key: stage,
      stage,
      round: null,
      label: humanize(stage),
    }));
    return [...pipelineLanes, ...terminalLanes];
  }, [selectedJob]);

  /** Open the detail dialog for the clicked card's application. */
  const handleOpen = useCallback((applicationId) => {
    setSelectedApplicationId(applicationId);
    setDialogOpen(true);
  }, []);

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
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold text-slate-900">Applications</h1>
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

      {!board ? (
        <LoadGate
          error={boardError}
          errorMessage="Couldn't load the board."
          onRetry={() => loadBoard(selectedJobId)}
        />
      ) : (
        <div className="flex flex-1 gap-4 overflow-x-auto pb-4">
          {lanes.map((lane) => {
            const cardsForStage = board[lane.stage] ?? [];
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
            return (
              <div
                key={lane.key}
                data-testid={`lane-${lane.key}`}
                className="flex w-72 shrink-0 flex-col gap-3 rounded-lg bg-slate-50 p-3"
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-slate-900">
                    {lane.label}
                  </h2>
                  <Badge variant="secondary">{cards.length}</Badge>
                </div>
                {cards.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No applicants</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {cards.map((card) => (
                      <ApplicantCard
                        key={card.id}
                        card={card}
                        showStatus={!isTerminal}
                        onOpen={handleOpen}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <ApplicantDetailDialog
        applicationId={selectedApplicationId}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onChanged={() => loadBoard(selectedJobId)}
        jobStages={selectedJob?.stages.map((s) => s.stage) ?? []}
        stageRounds={Object.fromEntries(
          (selectedJob?.stages ?? []).map((s) => [s.stage, s.rounds]),
        )}
      />
    </div>
  );
};

export default BoardPage;
