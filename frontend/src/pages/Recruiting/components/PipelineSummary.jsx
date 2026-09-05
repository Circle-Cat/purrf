import { Fragment } from "react";
import { Badge } from "@/components/ui/badge";
import { unavailablePersonLabel } from "@/pages/Recruiting/components/personLabel";

/** Human label for a stage key, e.g. "recruiter_screening" -> "Recruiter screening". */
const stageLabel = (key) =>
  String(key ?? "")
    .replace(/_/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase());

/** true when id isn't in pool: not selectable by this viewer, for reasons the viewer may not be told. */
const isUnresolved = (pool, id) => !pool.some((p) => p.userId === id);

/** "Name (#id)" when resolved, else "User {id} — unavailable". */
const personLabel = (pool, id) => {
  if (id == null) return null;
  const u = pool.find((p) => p.userId === id);
  return u ? `${u.name} (#${id})` : unavailablePersonLabel(id);
};

/**
 * Reviewer-facing readable summary of a posting's interview pipeline: owners
 * and the ordered stages with sessions and assignee tags.
 * Owner and default-assignee ids are resolved to names via the provided
 * pools. An id no longer in its pool renders in red with an 'unavailable'
 * suffix instead of a resolved name; the label does not say why it didn't
 * resolve.
 *
 * @param {{pipelineConfig?: {ownerIds?: number[], ownerId?: number,
 *          stages?: object[]},
 *          interviewPool?: object[], jobOwners?: object[]}} props
 */
const PipelineSummary = ({
  pipelineConfig,
  interviewPool = [],
  jobOwners = [],
}) => {
  const stages = pipelineConfig?.stages ?? [];
  // Legacy postings stored a single `ownerId`; new ones store `ownerIds`.
  const ownerIds =
    pipelineConfig?.ownerIds ??
    (pipelineConfig?.ownerId != null ? [pipelineConfig.ownerId] : []);
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-700">Interview pipeline</p>
      {ownerIds.length > 0 && (
        <p className="text-sm text-slate-600">
          Recruiter:
          {ownerIds.map((id, i) => (
            <Fragment key={id}>
              {i === 0 ? " " : ", "}
              {isUnresolved(jobOwners, id) ? (
                <span className="text-red-600">
                  {personLabel(jobOwners, id)}
                </span>
              ) : (
                personLabel(jobOwners, id)
              )}
            </Fragment>
          ))}
        </p>
      )}
      {stages.length === 0 ? (
        <p className="text-sm text-slate-400">No stages configured.</p>
      ) : (
        <ol className="space-y-1">
          {stages.map((s, i) => (
            <li
              key={`${s.stage ?? "stage"}-${i}`}
              className="flex flex-wrap items-center gap-2 text-sm text-slate-700"
            >
              <span>{`${i + 1}. ${stageLabel(s.stage)} — ${s.rounds ?? 1} ${
                (s.rounds ?? 1) === 1 ? "session" : "sessions"
              }`}</span>
              {s.defaultAssigneeId != null && (
                <Badge
                  variant={
                    isUnresolved(interviewPool, s.defaultAssigneeId)
                      ? "destructive"
                      : "outline"
                  }
                >
                  Assignee {personLabel(interviewPool, s.defaultAssigneeId)}
                </Badge>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
};

export default PipelineSummary;
