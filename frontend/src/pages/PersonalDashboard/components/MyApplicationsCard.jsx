import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/** Human-readable label for an ApplicationStage value, e.g. "hired" -> "Hired". */
const formatStageLabel = (stage) => {
  if (!stage) return "";
  const words = stage.split("_").join(" ");
  return words[0].toUpperCase() + words.slice(1);
};

/**
 * MyApplicationsCard
 *
 * Lists every application the current user has ever submitted, any job
 * kind, on Personal Dashboard. Clicking a row navigates to that
 * application's existing detail page (`MyApplication.jsx`) — this card
 * only renders the list, it doesn't duplicate the detail view.
 *
 * @param {{
 *   applications: Array<{applicationId: number, jobId: number, jobTitle: string, stage: string}>,
 *   isLoading: boolean,
 *   loadError: boolean,
 *   onRetry?: () => void,
 * }} props
 */
const MyApplicationsCard = ({
  applications,
  isLoading,
  loadError,
  onRetry,
}) => {
  const navigate = useNavigate();

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
        {!isLoading && !loadError && applications.length === 0 && (
          <p className="text-sm text-muted-foreground">No applications yet.</p>
        )}
        {!isLoading && !loadError && applications.length > 0 && (
          <ul className="divide-y divide-gray-100">
            {applications.map((app) => (
              <li key={app.applicationId}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between py-2 text-left hover:bg-gray-50"
                  onClick={() =>
                    navigate(ROUTE_PATHS.RECRUITING_MY_APPLICATION(app.jobId))
                  }
                >
                  <span className="text-sm text-slate-900">{app.jobTitle}</span>
                  <span className="text-sm text-muted-foreground">
                    {formatStageLabel(app.stage)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
};

export default MyApplicationsCard;
