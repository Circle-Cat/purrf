import { humanize } from "@/pages/Recruiting/board/stageFormat";
import PipelineSummary from "@/pages/Recruiting/components/PipelineSummary";

const ACTION_LABEL = {
  reject: "Reject",
  qualify: "Qualify",
  auto_hire: "Auto-hire",
};

/** "google.com" for a single value, "one of google.com, circlecat.org" for a list. */
const domainsPhrase = (value) =>
  Array.isArray(value) ? `one of ${value.join(", ")}` : value;

/** Human-readable description of one screen rule's condition. */
const describeCondition = (condition, questions) => {
  if (condition?.source === "email_domain") {
    return condition.operator === "not_in"
      ? `email domain is not ${domainsPhrase(condition.value)}`
      : `email domain is ${domainsPhrase(condition.value)}`;
  }
  if (condition?.source === "answer") {
    const question = questions.find((q) => q.id === condition.questionId);
    const label = question?.label || condition.questionId;
    return `answer to "${label}" is "${condition.value}"`;
  }
  return "an unrecognized condition";
};

/**
 * Read-only summary of a posting's pipeline/screening/profile configuration.
 * Shown to every viewer of the Configuration tab regardless of write access —
 * only the "Edit configuration" button next to it is permission-gated.
 *
 * @param {{job: {pipelineConfig?: object, screenRules?: object,
 *          profileConfig?: object, formSchema?: {questions?: object[]}},
 *          interviewPool?: object[], jobOwners?: object[]}} props
 */
const PostingConfigSummary = ({ job, interviewPool = [], jobOwners = [] }) => {
  const rules = job.screenRules?.rules ?? [];
  const questions = job.formSchema?.questions ?? [];
  const profile = job.profileConfig ?? {};

  return (
    <div className="space-y-4">
      <PipelineSummary
        pipelineConfig={job.pipelineConfig}
        interviewPool={interviewPool}
        jobOwners={jobOwners}
      />
      <div className="space-y-1">
        <h3 className="text-sm font-medium text-slate-700">Screening rules</h3>
        {rules.length === 0 ? (
          <p className="text-sm text-slate-400">No screening rules.</p>
        ) : (
          <ul className="space-y-1">
            {rules.map((r) => (
              <li key={r.id} className="text-sm text-slate-700">
                {ACTION_LABEL[r.action] ?? r.action} if{" "}
                {describeCondition(r.condition, questions)}
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
