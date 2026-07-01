import { Badge } from "@/components/ui/badge";

/** Human label for a stage key, e.g. "recruiter_screening" -> "Recruiter screening". */
const stageLabel = (key) =>
  String(key ?? "")
    .replace(/_/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase());

/**
 * Reviewer-facing readable summary of a posting's interview pipeline: owner and
 * the ordered stages with rounds, referral-skippable and assignee tags.
 *
 * @param {{pipelineConfig?: {ownerId?: number, stages?: object[]}}} props
 */
const PipelineSummary = ({ pipelineConfig }) => {
  const stages = pipelineConfig?.stages ?? [];
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-700">Interview pipeline</p>
      {pipelineConfig?.ownerId != null && (
        <p className="text-sm text-slate-600">
          Owner: #{pipelineConfig.ownerId}
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
                <Badge variant="outline">Assignee #{s.defaultAssigneeId}</Badge>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
};

export default PipelineSummary;
