import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import LoadGate from "@/pages/Recruiting/components/LoadGate";
import { listPublicJobs } from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * Logged-in browse page for published jobs: one card per posting
 * (title, kind, clamped description) linking to the candidate job-detail
 * page. Requires no recruiting permissions.
 */
const JobsBrowse = () => {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState(null);
  const [loadError, setLoadError] = useState(false);

  /** Fetch (or re-fetch, via Retry) the published-jobs summaries. */
  const load = useCallback(async () => {
    setLoadError(false);
    setJobs(null);
    try {
      const { data } = await listPublicJobs();
      setJobs(data ?? []);
    } catch (e) {
      setLoadError(true);
      toast.error(e.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (!jobs) {
    return (
      <LoadGate
        error={loadError}
        errorMessage="Couldn't load open positions."
        onRetry={load}
      />
    );
  }

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-xl font-semibold text-slate-900">Open Positions</h1>
      {jobs.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No open positions right now.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {jobs.map((job) => (
            <button
              key={job.id}
              type="button"
              onClick={() =>
                navigate(ROUTE_PATHS.RECRUITING_JOB_DETAIL(job.id))
              }
              className="rounded-lg border border-slate-200 p-4 text-left transition-colors hover:bg-slate-50"
            >
              <p className="font-medium text-slate-900">{job.title}</p>
              <p className="text-xs text-slate-500 capitalize">{job.kind}</p>
              {job.description && (
                <p className="mt-2 line-clamp-3 text-sm text-slate-700">
                  {job.description}
                </p>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default JobsBrowse;
