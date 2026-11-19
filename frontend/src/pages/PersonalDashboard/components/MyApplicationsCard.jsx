import { Link, useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { GLOSSARY, stageTermId } from "@/pages/Recruiting/components/glossary";

/** Human-readable label for an ApplicationStage value, from the recruiting
 * glossary so this card and the application page cannot name a stage
 * differently. Rendered as plain text: the row is itself a button, and a
 * tooltip trigger inside it would nest one control in another. */
const formatStageLabel = (stage, jobKind) =>
  GLOSSARY[stageTermId(stage, jobKind)]?.label ?? "";

const NO_NEXT_STEP_STAGES = ["rejected", "blacklisted"];

/**
 * What a mentorship applicant has left to do, for one row. Once admitted,
 * the details live in the Mentorship section of this page, so the row only
 * points there. Rows for any other posting, and closed-out applications,
 * get nothing.
 *
 * @param {{jobKind: string, mentorshipRole: string|null, stage: string}} app
 * @returns {string|null}
 */
const nextStepFor = (app) => {
  if (app.jobKind !== "activity" || !app.mentorshipRole) return null;
  if (NO_NEXT_STEP_STAGES.includes(app.stage)) return null;
  if (app.stage === "hired") return "Your next steps are in Mentorship below";
  return "We'll email you the decision";
};

/**
 * MyApplicationsCard
 *
 * Lists every application the current user has ever submitted, any job
 * kind, on Personal Dashboard. Clicking a row navigates to that
 * application's existing detail page (`MyApplication.jsx`) — this card
 * only renders the list, it doesn't duplicate the detail view.
 *
 * A mentorship row also says what comes next (see `nextStepFor`), under
 * the row rather than inside it, since the row is already a button.
 *
 * Saved, unsubmitted drafts are listed above the applications, marked
 * "Draft". One whose posting still takes applications leads back to the
 * apply route; one whose posting has closed is shown but not clickable,
 * since the job page cannot be loaded by someone who never applied. The
 * empty state shows only when there are neither applications nor drafts.
 *
 * @param {{
 *   applications: Array<{applicationId: number, jobId: number, jobTitle: string, stage: string, jobKind: string, mentorshipRole: string|null}>,
 *   drafts?: Array<{jobId: number, jobTitle: string, acceptingApplications: boolean}>,
 *   isLoading: boolean,
 *   loadError: boolean,
 *   onRetry?: () => void,
 * }} props
 */
const MyApplicationsCard = ({
  applications,
  drafts = [],
  isLoading,
  loadError,
  onRetry,
}) => {
  const navigate = useNavigate();
  const hasRows = applications.length > 0 || drafts.length > 0;

  return (
    <Card className="border-gray-200 shadow-sm">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">My Applications</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!isLoading && loadError && (
          <div className="flex flex-col items-start gap-3">
            <p className="text-sm text-muted-foreground">
              Couldn't load your applications.
            </p>
            <Button onClick={onRetry}>Retry</Button>
          </div>
        )}
        {!isLoading && !loadError && !hasRows && (
          <p className="text-sm text-muted-foreground">
            No applications yet.{" "}
            <Link
              to={ROUTE_PATHS.RECRUITING_JOBS_BROWSE}
              className="text-primary underline-offset-4 hover:underline"
            >
              Browse Open Positions
            </Link>{" "}
            to apply for a program or a job.
          </p>
        )}
        {!isLoading && !loadError && hasRows && (
          <ul className="divide-y divide-gray-100">
            {drafts.map((draft) => {
              const label = (
                <>
                  <span className="text-sm text-slate-900">
                    {draft.jobTitle}
                  </span>
                  <span className="text-sm text-muted-foreground">Draft</span>
                </>
              );
              return (
                <li key={`draft-${draft.jobId}`} className="py-2">
                  {draft.acceptingApplications ? (
                    <button
                      type="button"
                      className="flex w-full items-center justify-between text-left hover:bg-gray-50"
                      onClick={() =>
                        navigate(ROUTE_PATHS.RECRUITING_JOB_APPLY(draft.jobId))
                      }
                    >
                      {label}
                    </button>
                  ) : (
                    <div className="flex w-full items-center justify-between">
                      {label}
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {draft.acceptingApplications
                      ? "Not submitted yet"
                      : "This position has closed"}
                  </p>
                </li>
              );
            })}
            {applications.map((app) => {
              const nextStep = nextStepFor(app);
              return (
                <li key={app.applicationId} className="py-2">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between text-left hover:bg-gray-50"
                    onClick={() =>
                      navigate(ROUTE_PATHS.RECRUITING_MY_APPLICATION(app.jobId))
                    }
                  >
                    <span className="text-sm text-slate-900">
                      {app.jobTitle}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {formatStageLabel(app.stage, app.jobKind)}
                    </span>
                  </button>
                  {nextStep && (
                    <p className="text-xs text-muted-foreground">{nextStep}</p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
};

export default MyApplicationsCard;
