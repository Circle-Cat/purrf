import { RecordedValue } from "@/pages/Recruiting/components/RecordedValue";
import FormRenderer from "@/pages/Recruiting/postings/FormRenderer";
import {
  isVisible,
  otherSelected,
} from "@/pages/Recruiting/postings/questionVisibility";

/** Sibling-key suffix holding an "Other" option's free text. */
const OTHER_SUFFIX = "__other";

/**
 * Answer keys that `FormRenderer` will not display, given the question set it
 * is about to render. This is a *key*-level claim, and it holds only because
 * `FormRenderer`'s read-only rendering is total: a visible question shows its
 * recorded value whatever shape that value has (see `RecordedValue` and
 * `RetiredChoice` there), so a rendered key is never a silently dropped
 * answer. Covered here: answers to questions since deleted from the form,
 * answers left behind under a question a showWhen rule now hides, and a
 * `__other` sibling left over from a question whose primary answer no longer
 * selects that question's "Other" option (so `FormRenderer` no longer shows
 * the free text either).
 *
 * @param {Record<string, unknown>} answers
 * @param {object[]} questions
 * @returns {[string, unknown][]} Entries in `answers` insertion order.
 */
const unmatchedEntries = (answers, questions) => {
  const rendered = new Set();
  questions
    .filter((q) => isVisible(q, answers))
    .forEach((q) => {
      rendered.add(q.id);
      if (otherSelected(q, answers[q.id])) {
        rendered.add(`${q.id}${OTHER_SUFFIX}`);
      }
    });
  return Object.entries(answers).filter(([key]) => !rendered.has(key));
};

/**
 * A submitted application's answers, rendered through the very form the
 * candidate filled in (`FormRenderer` in read-only mode) so a reviewer sees
 * the questions in their authored order, the options that were *not* picked,
 * and every line break the candidate typed.
 *
 * Labels come from the submission's own schema snapshot when it has one. A
 * job's `form_schema` is overwritten in place whenever an owner edits the
 * posting and no historical copy is kept, so labeling an old answer with the
 * live schema can attribute it to a question that was never asked — when
 * that fallback is in play, the section says so rather than doing it quietly.
 *
 * `viewerIsApplicant` marks the one call site where the reader is the
 * candidate looking at their own application (`MyApplication`). Both
 * explanatory notices are internal data-quality caveats addressed to a
 * reviewer — one of them says "this candidate" — and neither carries an
 * action for the applicant, so they are suppressed there. Everything else,
 * including the "Other recorded answers" group and its contents, still
 * renders: hiding a candidate's own recorded answers would break the same
 * guarantee the group exists to keep.
 *
 * @param {{submission: {answers?: object, formSchema?: {questions: object[]}}|undefined,
 *          liveQuestions?: object[],
 *          idPrefix?: string,
 *          viewerIsApplicant?: boolean}} props
 */
const AnswersSection = ({
  submission,
  liveQuestions = [],
  idPrefix = "",
  viewerIsApplicant = false,
}) => {
  const answers = submission?.answers ?? {};
  const snapshotQuestions = submission?.formSchema?.questions;
  const questions = snapshotQuestions ?? liveQuestions;
  const fromLive = snapshotQuestions == null;
  const unmatched = unmatchedEntries(answers, questions);

  if (questions.length === 0 && unmatched.length === 0) return null;

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-medium text-slate-700">Answers</h2>
      {fromLive && questions.length > 0 && !viewerIsApplicant && (
        <p className="text-xs text-slate-500">
          Labels are from the job&apos;s current form, not the version this
          candidate filled in.
        </p>
      )}
      <FormRenderer
        readOnly
        questions={questions}
        answers={answers}
        idPrefix={idPrefix}
      />
      {unmatched.length > 0 && (
        <div className="space-y-2 pt-2">
          <h3 className="text-xs font-semibold uppercase text-slate-500">
            Other recorded answers
          </h3>
          {!viewerIsApplicant && (
            <p className="text-xs text-slate-500">
              These questions were removed from the form, or are hidden by a
              conditional rule.
            </p>
          )}
          {unmatched.map(([key, value]) => (
            <div key={key} className="space-y-1">
              <p className="text-sm font-medium text-slate-700">{key}</p>
              <RecordedValue value={value} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AnswersSection;
