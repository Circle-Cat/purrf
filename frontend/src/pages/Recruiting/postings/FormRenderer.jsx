import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/**
 * True when a question with a showWhen rule should be visible given answers.
 *
 * @param {object} question
 * @param {Record<string, string|string[]>} answers
 * @returns {boolean}
 */
const isVisible = (question, answers) => {
  if (!question.showWhen) return true;
  const dep = answers[question.showWhen.questionId];
  const target = question.showWhen.equals;
  return Array.isArray(dep) ? dep.includes(target) : dep === target;
};

/**
 * Renders a single question's control based on its type.
 *
 * @param {{question: object, value: string|string[]|undefined,
 *          otherValue: string|undefined,
 *          onAnswerChange: (id: string, value: string|string[]) => void}} props
 */
const QuestionControl = ({ question, value, otherValue, onAnswerChange }) => {
  const { id, type, label, options = [] } = question;
  const set = (v) => onAnswerChange(id, v);

  const otherSelected =
    question.otherOption != null &&
    (type === "multi_choice"
      ? Array.isArray(value) && value.includes(question.otherOption)
      : value === question.otherOption);
  const specifyInput = otherSelected ? (
    <div className="space-y-1">
      <Label htmlFor={`${id}__other`}>
        {question.otherOption}
        <span className="ml-1 text-red-500">*</span>
      </Label>
      <Input
        id={`${id}__other`}
        aria-label={`${question.otherOption} (please specify)`}
        value={otherValue ?? ""}
        onChange={(e) => onAnswerChange(`${id}__other`, e.target.value)}
      />
    </div>
  ) : null;

  if (type === "long_text") {
    return (
      <Textarea
        id={id}
        aria-label={label}
        value={value ?? ""}
        onChange={(e) => set(e.target.value)}
      />
    );
  }
  if (type === "single_choice") {
    return (
      <div className="space-y-2">
        <div role="radiogroup" aria-label={label} className="space-y-1">
          {options
            .filter((opt) => opt && opt.trim() !== "")
            .map((opt) => (
              <label key={opt} className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name={id}
                  value={opt}
                  checked={value === opt}
                  onChange={() => set(opt)}
                />
                {opt}
              </label>
            ))}
        </div>
        {specifyInput}
      </div>
    );
  }
  if (type === "multi_choice") {
    const selected = Array.isArray(value) ? value : [];
    const toggle = (opt) =>
      set(
        selected.includes(opt)
          ? selected.filter((o) => o !== opt)
          : [...selected, opt],
      );
    return (
      <div className="space-y-2">
        <div role="group" aria-label={label} className="space-y-1">
          {options
            .filter((opt) => opt && opt.trim() !== "")
            .map((opt) => (
              <label key={opt} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  value={opt}
                  checked={selected.includes(opt)}
                  onChange={() => toggle(opt)}
                />
                {opt}
              </label>
            ))}
        </div>
        {specifyInput}
      </div>
    );
  }
  // short_text and exact_text both render a single-line text input.
  return (
    <Input
      id={id}
      aria-label={label}
      value={value ?? ""}
      onChange={(e) => set(e.target.value)}
    />
  );
};

/**
 * Shared, controlled renderer for a posting's submission form. Renders the five
 * question types and applies single-layer showWhen visibility. Preview/consumer
 * decides what to do with answers; this component never submits.
 *
 * @param {{questions: object[],
 *          answers: Record<string, string|string[]>,
 *          onAnswerChange: (id: string, value: string|string[]) => void}} props
 */
const FormRenderer = ({ questions = [], answers = {}, onAnswerChange }) => (
  <div className="space-y-4">
    {questions
      .filter((q) => isVisible(q, answers))
      .map((q) => (
        <div key={q.id} className="space-y-1">
          <Label
            {...(["short_text", "long_text", "exact_text"].includes(q.type)
              ? { htmlFor: q.id }
              : {})}
          >
            {q.label}
            {q.required && <span className="ml-1 text-red-500">*</span>}
          </Label>
          <QuestionControl
            question={q}
            value={answers[q.id]}
            otherValue={answers[`${q.id}__other`]}
            onAnswerChange={onAnswerChange}
          />
        </div>
      ))}
  </div>
);

export default FormRenderer;
