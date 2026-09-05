import { Fragment } from "react";
import { Badge } from "@/components/ui/badge";

/** Human label for a stage key, e.g. "recruiter_screening" -> "Recruiter screening". */
const stageLabel = (key) =>
  String(key ?? "")
    .replace(/_/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase());

/** true when id isn't in pool: lost (or never had) the permission that made them pickable. */
const isUnresolved = (pool, id) => !pool.some((p) => p.userId === id);

/**
 * "User {id}", for an unresolved person with no action available to the
 * viewer -- e.g. a historical evaluator, who can't be removed.
 */
export const unresolvedPersonLabel = (id) => `User ${id}`;

/**
 * "User {id} — unavailable, remove", for an unresolved person the viewer
 * can remove. Deliberately silent on why the id didn't resolve: that reason
 * (revoked permission, or a sanction only account admins may see) isn't the
 * viewer's to know.
 */
export const unresolvedPersonLabelWithAction = (id) =>
  `${unresolvedPersonLabel(id)} — unavailable, remove`;

/** "Name (#id)" when resolved, else "User {id} — unavailable, remove". */
const personLabel = (pool, id) => {
  if (id == null) return null;
  const u = pool.find((p) => p.userId === id);
  return u ? `${u.name} (#${id})` : unresolvedPersonLabelWithAction(id);
};

/**
 * Reviewer-facing readable summary of a posting's interview pipeline: owners
 * and the ordered stages with sessions and assignee tags.
 * Owner and default-assignee ids are resolved to names via the provided
 * pools. An id no longer in its pool renders in red with an 'unavailable,
 * remove' suffix instead of a resolved name; the label does not say why
 * it didn't resolve.
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
