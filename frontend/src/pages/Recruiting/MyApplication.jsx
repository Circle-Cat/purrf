import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import { getPublicJob, getMyApplication } from "@/api/recruitingApi";
import ApplicationForm from "@/pages/Recruiting/ApplicationForm";
import LoadGate from "@/pages/Recruiting/components/LoadGate";
import { RowList } from "@/pages/Recruiting/components/ApplicationSnapshotRows";

/** The only stage at which a candidate's application is still editable. */
const EDITABLE_STAGE = "applied";

/**
 * Human-readable label for an `ApplicationStage` enum value, e.g.
 * "recruiter_screening" -> "Recruiter screening".
 *
 * @param {string} stage
 * @returns {string}
 */
const formatStageLabel = (stage) => {
  if (!stage) return "";
  const words = stage.split("_").join(" ");
  return words[0].toUpperCase() + words.slice(1);
};

/**
 * Read-only summary of a submitted application: the applicant's answers, no
 * longer editable once the application has moved past the `applied` stage.
 *
 * @param {{job: object, application: object}} props
 */
const ReadOnlySummary = ({ job, application }) => {
  const submission = application.current?.submission ?? {};
  const personal = submission.personal ?? {};
  const answers = submission.answers ?? {};
  const questions = job.formSchema?.questions ?? [];

  return (
    <div className="space-y-4 p-6">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-slate-900">{job.title}</h1>
        <p className="text-sm text-slate-600">
          Status: {formatStageLabel(application.stage)}
        </p>
      </div>
      <div className="space-y-1">
        <h2 className="text-sm font-medium text-slate-700">Personal</h2>
        <p className="text-sm text-slate-700">
          {[personal.firstName, personal.lastName].filter(Boolean).join(" ") ||
            "Not provided."}
        </p>
      </div>
      <RowList title="Education" rows={submission.education ?? []} />
      <RowList title="Experience" rows={submission.experience ?? []} />
      {questions.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-slate-700">Answers</h2>
          <ul className="space-y-1">
            {questions.map((q) => (
              <li key={q.id} className="text-sm text-slate-700">
                {q.label}: {String(answers[q.id] ?? "—")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

/**
 * The signed-in candidate's own application for a job: a new/editable
 * `ApplicationForm` while the application has no stage yet or is still at
 * the `applied` stage, otherwise a read-only summary of what was submitted.
 * Loads the job and application on mount; while loading shows a placeholder,
 * and on failure toasts the error and shows an inline retryable error state.
 */
const MyApplication = () => {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [application, setApplication] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState(false);

  /** Load (or reload, after a failure) the job and the caller's application. */
  const load = useCallback(() => {
    setLoadError(false);
    setLoaded(false);
    Promise.all([getPublicJob(jobId), getMyApplication(jobId)])
      .then(([jobRes, appRes]) => {
        setJob(jobRes.data);
        setApplication(appRes.data ?? null);
        setLoaded(true);
      })
      .catch((e) => {
        setLoadError(true);
        toast.error(e.message);
      });
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  if (!loaded || !job) {
    return (
      <LoadGate
        error={loadError}
        errorMessage="Couldn't load your application."
        onRetry={load}
      />
    );
  }

  if (!application || application.stage === EDITABLE_STAGE) {
    return (
      <div className="space-y-4 p-6">
        <ApplicationForm
          job={job}
          existing={application ?? undefined}
          onSubmitted={setApplication}
        />
      </div>
    );
  }

  return <ReadOnlySummary job={job} application={application} />;
};

export default MyApplication;
