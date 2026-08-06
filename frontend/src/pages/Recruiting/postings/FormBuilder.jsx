import { Button } from "@/components/ui/button";
import QuestionEditor from "@/pages/Recruiting/postings/QuestionEditor";
import {
  QUESTION_TYPES,
  addQuestion,
  addOption,
  renameOption,
  removeOption,
  revealQuestion,
  clearCondition,
} from "@/pages/Recruiting/postings/questionTypes";

/**
 * Ordered submission-form builder: add (per type), remove, reorder questions.
 *
 * Takes and emits the whole form schema rather than just the questions array,
 * so the monotonic `nextSeq` counter survives every edit -- and because an
 * option edit is a whole-form operation: options are referenced by text from
 * the `showWhen` of every question they reveal, so one keystroke in an option
 * has to rewrite other questions in the same edit.
 *
 * @param {{formSchema: {questions?: object[], nextSeq?: number},
 *          onChange: (next: object) => void}} props
 */
const FormBuilder = ({ formSchema = { questions: [] }, onChange }) => {
  const questions = formSchema.questions ?? [];
  const emit = (next) => onChange({ ...formSchema, questions: next });
  const add = (type) => onChange(addQuestion(formSchema, type));
  const updateAt = (i, q) =>
    emit(questions.map((cur, idx) => (idx === i ? q : cur)));
  const removeAt = (i) => emit(questions.filter((_, idx) => idx !== i));
  /**
   * The whole-form operations `QuestionEditor` drives from `parent`'s options.
   * Each returns a complete next schema, so an edit that touches both the
   * option and the questions it reveals lands as one change.
   */
  const optionOps = (parent) => ({
    add: () => onChange(addOption(formSchema, parent.id)),
    rename: (i, value) =>
      onChange(renameOption(formSchema, parent.id, i, value)),
    remove: (i) => onChange(removeOption(formSchema, parent.id, i)),
    reveal: (option, questionId) =>
      onChange(revealQuestion(formSchema, questionId, parent.id, option)),
    hide: (questionId) => onChange(clearCondition(formSchema, questionId)),
  });
  const move = (i, delta) => {
    const j = i + delta;
    if (j < 0 || j >= questions.length) return;
    const next = [...questions];
    [next[i], next[j]] = [next[j], next[i]];
    emit(next);
  };

  return (
    <div className="space-y-4">
      {questions.map((q, i) => (
        <QuestionEditor
          key={q.id}
          question={q}
          allQuestions={questions}
          onChange={(updated) => updateAt(i, updated)}
          onRemove={() => removeAt(i)}
          onMoveUp={() => move(i, -1)}
          onMoveDown={() => move(i, 1)}
          optionOps={optionOps(q)}
        />
      ))}
      {/* Below the questions, like the Add rule buttons in ScreenRulesEditor:
          a new question appends to the end, so the control that adds it stays
          next to where it lands instead of scrolling out of reach. */}
      <div className="flex flex-wrap gap-2">
        {QUESTION_TYPES.map((t) => (
          <Button
            key={t.value}
            type="button"
            variant="outline"
            size="sm"
            onClick={() => add(t.value)}
          >
            Add {t.label}
          </Button>
        ))}
      </div>
    </div>
  );
};

export default FormBuilder;
