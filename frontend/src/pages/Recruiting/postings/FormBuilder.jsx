import { Button } from "@/components/ui/button";
import QuestionEditor from "@/pages/Recruiting/postings/QuestionEditor";
import {
  QUESTION_TYPES,
  blankQuestion,
} from "@/pages/Recruiting/postings/questionTypes";

/**
 * Ordered submission-form builder: add (per type), remove, reorder questions.
 *
 * @param {{questions: object[], onChange: (next: object[]) => void}} props
 */
const FormBuilder = ({ questions = [], onChange }) => {
  const add = (type) =>
    onChange([...questions, blankQuestion(type, questions)]);
  const updateAt = (i, q) =>
    onChange(questions.map((cur, idx) => (idx === i ? q : cur)));
  const removeAt = (i) => onChange(questions.filter((_, idx) => idx !== i));
  const move = (i, delta) => {
    const j = i + delta;
    if (j < 0 || j >= questions.length) return;
    const next = [...questions];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
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
