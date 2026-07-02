import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { getPublicJob, getMyApplication } from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import ApplicationForm from "@/pages/Recruiting/ApplicationForm";
import LoadGate from "@/pages/Recruiting/components/LoadGate";

/**
 * Candidate-facing published-job screen, registered at both
 * `/recruiting/jobs/:jobId` (summary + Apply action) and
 * `/recruiting/jobs/:jobId/apply` (the new-application form) so both routes
 * share one load of the public job. Loads the job on mount via
 * `getPublicJob`; while loading shows a placeholder, and on failure toasts
 * the error and shows an inline retryable error state.
 *
 * The apply route additionally checks `getMyApplication` before rendering
 * the form: a candidate who already has an application is redirected to the
 * my-application route instead of dead-ending on a blank form that would
 * 422 on submit. A failed check falls back to showing the form -- the
 * submit path still surfaces backend errors.
 */
const JobDetailPage = () => {
  const { jobId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const isApplying = location.pathname.endsWith("/apply");
  const [checkingExisting, setCheckingExisting] = useState(isApplying);
  const [hasExisting, setHasExisting] = useState(false);

  /** Load (or reload, after a failure) the public job into state. */
  const load = useCallback(() => {
    setLoadError(false);
    setJob(null);
    getPublicJob(jobId)
      .then(({ data }) => setJob(data))
      .catch((e) => {
        setLoadError(true);
        toast.error(e.message);
      });
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!isApplying) return;
    let cancelled = false;
    setCheckingExisting(true);
    getMyApplication(jobId)
      .then(({ data }) => {
        if (!cancelled) setHasExisting(Boolean(data));
      })
      .catch(() => {
        // Soft-fail: fall back to showing the form.
        if (!cancelled) setHasExisting(false);
      })
      .finally(() => {
        if (!cancelled) setCheckingExisting(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isApplying, jobId]);

  useEffect(() => {
    if (isApplying && hasExisting) {
      navigate(ROUTE_PATHS.RECRUITING_MY_APPLICATION(jobId), { replace: true });
    }
  }, [isApplying, hasExisting, jobId, navigate]);

  if (!job || (isApplying && (checkingExisting || hasExisting))) {
    return (
      <LoadGate
        error={loadError}
        errorMessage="Couldn't load this job."
        onRetry={load}
      />
    );
  }

  if (isApplying) {
    return (
      <div className="space-y-4 p-6">
        <ApplicationForm
          job={job}
          onSubmitted={() =>
            navigate(ROUTE_PATHS.RECRUITING_MY_APPLICATION(jobId))
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-4 p-6">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-slate-900">{job.title}</h1>
        <p className="text-sm text-slate-500 capitalize">{job.kind}</p>
      </div>
      {job.description && (
        <p className="text-sm whitespace-pre-line text-slate-700">
          {job.description}
        </p>
      )}
      <Button onClick={() => navigate(ROUTE_PATHS.RECRUITING_JOB_APPLY(jobId))}>
        Apply
      </Button>
    </div>
  );
};

export default JobDetailPage;
