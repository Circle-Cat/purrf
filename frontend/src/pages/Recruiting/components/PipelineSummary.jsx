import { Badge } from "@/components/ui/badge";

/** Human label for a stage key, e.g. "recruiter_screening" -> "Recruiter screening". */
const stageLabel = (key) =>
  String(key ?? "")
    .replace(/_/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase());

/** "Name (#id)" when the id resolves in the pool, else "#id" (or null when unset). */
const personLabel = (pool, id) => {
  if (id == null) return null;
  const u = pool.find((p) => p.userId === id);
  return u ? `${u.name} (#${id})` : `#${id}`;
};

/** Comma-separated "Name (#id)" labels for a list of owner ids. */
const personLabels = (pool, ids) =>
  ids.map((id) => personLabel(pool, id)).join(", ");

/**
 * Reviewer-facing readable summary of a posting's interview pipeline: owners
 * and the ordered stages with rounds, referral-skippable and assignee tags.
 * Owner and default-assignee ids are resolved to names via the provided
 * pools.
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
          Owner: {personLabels(jobOwners, ownerIds)}
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
              <span>{`${i + 1}. ${stageLabel(s.stage)} — ${s.rounds ?? 1} round(s)`}</span>
              {s.referralSkippable && (
                <Badge variant="outline">Referral-skippable</Badge>
              )}
              {s.defaultAssigneeId != null && (
                <Badge variant="outline">
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
