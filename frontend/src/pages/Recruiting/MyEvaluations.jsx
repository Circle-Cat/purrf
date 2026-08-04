import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import LoadGate from "@/pages/Recruiting/components/LoadGate";
import { listMyEvaluations } from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/** Human label for a stage key, e.g. "recruiter_screening" -> "Recruiter screening". */
const stageLabel = (key) =>
  String(key ?? "")
    .replace(/_/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase());

/**
 * List page of the current user's assigned interview evaluations, one row
 * per application/stage pairing they're the assignee for. Each row links to
 * the shared application detail page in `?mode=evaluate`, which renders only
 * the rubric form there — no owner actions, even if the caller also owns
 * the job. Route and nav entry are gated on RECRUITING_INTERVIEW_EVALUATE;
 * the backend list itself still scopes by assignment, not by permission.
 */
const MyEvaluations = () => {
  const [evaluations, setEvaluations] = useState(null);
  const [loadError, setLoadError] = useState(false);

  /** Fetch (or re-fetch, via Retry) the caller's assigned evaluations. */
  const load = useCallback(async () => {
    setLoadError(false);
    setEvaluations(null);
    try {
      const { data } = await listMyEvaluations();
      setEvaluations(data ?? []);
    } catch (e) {
      setLoadError(true);
      toast.error(e.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (!evaluations) {
    return (
      <LoadGate
        error={loadError}
        errorMessage="Couldn't load your evaluations."
        onRetry={load}
      />
    );
  }

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-xl font-semibold text-slate-900">
        My Interview Evaluations
      </h1>
      {evaluations.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          You have no assigned evaluations.
        </p>
      ) : (
        <div className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {evaluations.map((row) => {
            const key = `${row.applicationId}-${row.stage}-${row.round}`;
            const rowContent = (
              <>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">
                    {row.applicantName}
                  </p>
                  <p className="truncate text-xs text-slate-500">
                    {row.jobTitle}
                  </p>
                </div>
                <Badge variant="outline">
                  {stageLabel(row.stage)} — Round {row.round}
                </Badge>
                <Badge variant={row.isConfirmed ? "default" : "secondary"}>
                  {row.isConfirmed ? "Confirmed" : "Pending"}
                </Badge>
                {!row.isCurrent && (
                  <Badge variant="secondary">No longer assigned</Badge>
                )}
              </>
            );
            return row.isCurrent ? (
              <Link
                key={key}
                to={`${ROUTE_PATHS.RECRUITING_APPLICATION_DETAIL(row.applicationId)}?mode=evaluate`}
                className="flex items-center gap-3 p-4 no-underline transition-colors hover:bg-slate-50"
              >
                {rowContent}
              </Link>
            ) : (
              <div key={key} className="flex items-center gap-3 p-4">
                {rowContent}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default MyEvaluations;
