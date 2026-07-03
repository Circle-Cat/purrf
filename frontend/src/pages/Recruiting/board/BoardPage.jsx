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

/** Terminal lanes always appended after a job's configured pipeline stages. */
const TERMINAL_STAGES = ["hired", "rejected"];

/** "recruiter_screening" -> "Recruiter screening". */
const stageLabel = (stage) => {
  const spaced = stage.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
};

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
    return [...selectedJob.stages, ...TERMINAL_STAGES];
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
          {lanes.map((stage) => {
            const cards = board[stage] ?? [];
            const isTerminal = TERMINAL_STAGES.includes(stage);
            return (
              <div
                key={stage}
                data-testid={`lane-${stage}`}
                className="flex w-72 shrink-0 flex-col gap-3 rounded-lg bg-slate-50 p-3"
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-slate-900">
                    {stageLabel(stage)}
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
        jobStages={selectedJob?.stages ?? []}
      />
    </div>
  );
};

export default BoardPage;
