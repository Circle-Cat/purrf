import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { getPublicJob } from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import ApplicationForm from "@/pages/Recruiting/ApplicationForm";

/**
 * Candidate-facing published-job screen, registered at both
 * `/recruiting/jobs/:jobId` (summary + Apply action) and
 * `/recruiting/jobs/:jobId/apply` (the new-application form) so both routes
 * share one load of the public job. Loads the job on mount via
 * `getPublicJob` and toasts an error if that fails.
 */
const JobDetailPage = () => {
  const { jobId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const isApplying = location.pathname.endsWith("/apply");

  useEffect(() => {
    getPublicJob(jobId)
      .then(({ data }) => setJob(data))
      .catch((e) => toast.error(e.message));
  }, [jobId]);

  if (!job) return null;

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
