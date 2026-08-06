import { Button } from "@/components/ui/button";
import QuestionEditor from "@/pages/Recruiting/postings/QuestionEditor";
import {
  QUESTION_TYPES,
  addQuestion,
} from "@/pages/Recruiting/postings/questionTypes";

/**
 * Ordered submission-form builder: add (per type), remove, reorder questions.
 *
 * Takes and emits the whole form schema rather than just the questions array,
 * so the monotonic `nextSeq` counter survives every edit.
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
  const move = (i, delta) => {
    const j = i + delta;
    if (j < 0 || j >= questions.length) return;
    const next = [...questions];
    [next[i], next[j]] = [next[j], next[i]];
    emit(next);
  };

  return (
    <div className="space-y-4">
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
      {questions.map((q, i) => (
        <QuestionEditor
          key={q.id}
          question={q}
          allQuestions={questions}
          onChange={(updated) => updateAt(i, updated)}
          onRemove={() => removeAt(i)}
          onMoveUp={() => move(i, -1)}
          onMoveDown={() => move(i, 1)}
        />
      ))}
    </div>
  );
};

export default FormBuilder;
