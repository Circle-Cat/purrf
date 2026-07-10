import { humanize } from "@/pages/Recruiting/board/stageFormat";

/**
 * Read-only summary of a posting's pipeline/screening/profile configuration.
 * Shown to every viewer of the Configuration tab regardless of write access —
 * only the "Edit configuration" button next to it is permission-gated.
 *
 * @param {{job: {pipelineConfig?: object, screenRules?: object, profileConfig?: object}}} props
 */
const PostingConfigSummary = ({ job }) => {
  const stages = job.pipelineConfig?.stages ?? [];
  const rules = job.screenRules?.rules ?? [];
  const profile = job.profileConfig ?? {};

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h3 className="text-sm font-medium text-slate-700">
          Interview pipeline
        </h3>
        {stages.length === 0 ? (
          <p className="text-sm text-slate-400">
            No pipeline configured yet.
          </p>
        ) : (
          <ul className="space-y-1">
            {stages.map((s) => (
              <li key={s.stage} className="text-sm text-slate-700">
                {`${humanize(s.stage)} — ${s.rounds ?? 1} round${(s.rounds ?? 1) > 1 ? "s" : ""}`}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="space-y-1">
        <h3 className="text-sm font-medium text-slate-700">
          Screening rules
        </h3>
        {rules.length === 0 ? (
          <p className="text-sm text-slate-400">No screening rules.</p>
        ) : (
          <ul className="space-y-1">
            {rules.map((r) => (
              <li key={r.id} className="text-sm text-slate-700">
                {r.action} if {r.condition?.source} {r.condition?.question_id ?? ""}{" "}
                matches {JSON.stringify(r.condition?.value)}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="space-y-1">
        <h3 className="text-sm font-medium text-slate-700">
          Profile requirements
        </h3>
        <ul className="space-y-1">
          {["education", "experience", "resume"].map((field) => (
            <li key={field} className="text-sm text-slate-700">
              {humanize(field)}: {humanize(profile[field] ?? "off")}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default PostingConfigSummary;
