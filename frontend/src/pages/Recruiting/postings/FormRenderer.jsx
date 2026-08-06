import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RecordedValue } from "@/pages/Recruiting/components/RecordedValue";
import {
  otherSelected,
  visibleQuestions,
} from "@/pages/Recruiting/postings/questionVisibility";

/**
 * A recorded value as one line of text, for a choice row's label. Arrays join
 * on ", " and objects fall back to compact JSON, so neither degrades to
 * "[object Object]".
 *
 * @param {unknown} value
 * @returns {string}
 */
const answerLabel = (value) => {
  if (Array.isArray(value)) return value.map(answerLabel).join(", ");
  if (value !== null && typeof value === "object") return JSON.stringify(value);
  return value == null ? "" : String(value);
};

/**
 * True when a recorded value holds nothing worth showing, i.e. it is absent
 * or blank text. An array is never blank here — an empty one is a real "no
 * options picked" and the option list itself already says so.
 *
 * @param {unknown} value
 * @returns {boolean}
 */
const isBlankAnswer = (value) =>
  value == null || (typeof value === "string" && value.trim() === "");

/**
 * A recorded choice value the question's current option list no longer
 * contains: an option the owner has since deleted, or a value of the wrong
 * shape left behind by a type change. Rendered as a checked, disabled row so
 * it reads as something the candidate picked, marked so a reviewer cannot
 * mistake it for an option still on offer.
 *
 * Rendering it is what keeps the read-only view total — every recorded value
 * reaches the page, whether or not the live question can represent it.
 *
 * @param {{kind: "radio"|"checkbox", name?: string, value: unknown}} props
 */
const RetiredChoice = ({ kind, name, value }) => (
  <label className="flex items-center gap-2 text-sm font-medium">
    <input type={kind} name={name} checked disabled onChange={() => {}} />
    {answerLabel(value)}{" "}
    <span className="font-normal text-slate-500">(no longer an option)</span>
  </label>
);

/**
 * Renders a single question's control based on its type.
 *
 * In read-only mode the text types become text blocks, while the choice types
 * keep their full option list with the inputs disabled — an option the
 * candidate did *not* pick is part of what a reviewer needs to see.
 *
 * Read-only rendering is total: a recorded value the live question cannot
 * represent (an array under a text question, a value that is no longer one of
 * the options, a bare string under multi_choice) is still shown, because the
 * question a value was recorded under can change under it at any time and a
 * dropped answer would read as an affirmative claim the candidate never
 * answered.
 *
 * @param {{question: object, value: unknown,
 *          otherValue: unknown,
 *          onAnswerChange: (id: string, value: string|string[]) => void,
 *          readOnly?: boolean, idPrefix?: string}} props
 */
const QuestionControl = ({
  question,
  value,
  otherValue,
  onAnswerChange,
  readOnly = false,
  idPrefix = "",
}) => {
  const { id, type, label, options = [] } = question;
  const domId = `${idPrefix}${id}`;
  const set = (v) => onAnswerChange(id, v);
  const shownOptions = options.filter((opt) => opt && opt.trim() !== "");

  const specifyInput = otherSelected(question, value) ? (
    <div className="space-y-1">
      {readOnly ? (
        <p className="text-sm font-medium">{question.otherOption}</p>
      ) : (
        <Label htmlFor={`${domId}__other`}>
          {question.otherOption}
          <span className="ml-1 text-red-500">*</span>
        </Label>
      )}
      {readOnly ? (
        <RecordedValue value={otherValue} />
      ) : (
        <Input
          id={`${domId}__other`}
          aria-label={`${question.otherOption} (please specify)`}
          value={otherValue ?? ""}
          onChange={(e) => onAnswerChange(`${id}__other`, e.target.value)}
        />
      )}
    </div>
  ) : null;

  if (type === "long_text") {
    return readOnly ? (
      <RecordedValue value={value} />
    ) : (
      <Textarea
        id={domId}
        aria-label={label}
        value={value ?? ""}
        onChange={(e) => set(e.target.value)}
      />
    );
  }
  if (type === "single_choice") {
    // A recorded value no option can show. Kept whole rather than flattened:
    // an array here is a multi_choice answer left behind by a type change,
    // and a radio group can only ever mark one of its members. An *empty*
    // array is that same drift's "no options picked" and asserts nothing
    // about the candidate, so — unlike isBlankAnswer's array handling, which
    // is deliberately different for multi_choice — it must not surface here.
    const retired =
      readOnly &&
      !isBlankAnswer(value) &&
      (!Array.isArray(value) || value.length > 0) &&
      !shownOptions.includes(value)
        ? [value]
        : [];
    return (
      <div className="space-y-2">
        <div role="radiogroup" aria-label={label} className="space-y-1">
          {shownOptions.map((opt) => (
            <label
              key={opt}
              className={`flex items-center gap-2 text-sm ${
                readOnly && value === opt ? "font-medium" : ""
              }`}
            >
              <input
                type="radio"
                name={domId}
                value={opt}
                checked={value === opt}
                disabled={readOnly}
                onChange={readOnly ? () => {} : () => set(opt)}
              />
              {opt}
            </label>
          ))}
          {retired.map((v) => (
            <RetiredChoice
              key={answerLabel(v)}
              kind="radio"
              name={domId}
              value={v}
            />
          ))}
        </div>
        {specifyInput}
      </div>
    );
  }
  if (type === "multi_choice") {
    // A bare string here is a single_choice answer left behind by a type
    // change; treating it as a one-element selection is what checks its box
    // instead of showing the whole list unticked.
    const selected = Array.isArray(value)
      ? value
      : readOnly && !isBlankAnswer(value)
        ? [value]
        : [];
    const retired = readOnly
      ? selected.filter((v) => !shownOptions.includes(v))
      : [];
    const toggle = (opt) =>
      set(
        selected.includes(opt)
          ? selected.filter((o) => o !== opt)
          : [...selected, opt],
      );
    return (
      <div className="space-y-2">
        <div role="group" aria-label={label} className="space-y-1">
          {shownOptions.map((opt) => (
            <label
              key={opt}
              className={`flex items-center gap-2 text-sm ${
                readOnly && selected.includes(opt) ? "font-medium" : ""
              }`}
            >
              <input
                type="checkbox"
                value={opt}
                checked={selected.includes(opt)}
                disabled={readOnly}
                onChange={readOnly ? () => {} : () => toggle(opt)}
              />
              {opt}
            </label>
          ))}
          {retired.map((v) => (
            <RetiredChoice key={answerLabel(v)} kind="checkbox" value={v} />
          ))}
        </div>
        {specifyInput}
      </div>
    );
  }
  // short_text, exact_text, and any question predating the type field.
  return readOnly ? (
    <RecordedValue value={value} />
  ) : (
    <Input
      id={domId}
      aria-label={label}
      value={value ?? ""}
      onChange={(e) => set(e.target.value)}
    />
  );
};

/**
 * Shared renderer for a posting's submission form. Renders the five question
 * types and applies single-layer showWhen visibility.
 *
 * Controlled by default; pass `readOnly` to render a submitted set of answers
 * for review instead — `onAnswerChange` is then unused and may be omitted.
 * `idPrefix` namespaces the generated DOM ids so two copies (e.g. the
 * applicant's own answers plus an expanded other application) can coexist on
 * one page without colliding.
 *
 * @param {{questions: object[],
 *          answers: Record<string, unknown>,
 *          onAnswerChange?: (id: string, value: string|string[]) => void,
 *          readOnly?: boolean, idPrefix?: string}} props
 */
const FormRenderer = ({
  questions = [],
  answers = {},
  onAnswerChange = () => {},
  readOnly = false,
  idPrefix = "",
}) => (
  <div className="space-y-4">
    {visibleQuestions(questions, answers).map((q) => (
      <div key={q.id} className="space-y-1">
        {readOnly ? (
          // A <Label> here would label no control (read-only text answers
          // are not inputs), and the required marker is a form-filling
          // affordance a reviewer takes no action on.
          <p className="text-sm font-medium">{q.label}</p>
        ) : (
          <Label
            {...(["short_text", "long_text", "exact_text"].includes(q.type)
              ? { htmlFor: `${idPrefix}${q.id}` }
              : {})}
          >
            {q.label}
            {q.required && <span className="ml-1 text-red-500">*</span>}
          </Label>
        )}
        {q.description && (
          <p className="text-sm text-slate-500">{q.description}</p>
        )}
        <QuestionControl
          question={q}
          value={answers[q.id]}
          otherValue={answers[`${q.id}__other`]}
          onAnswerChange={onAnswerChange}
          readOnly={readOnly}
          idPrefix={idPrefix}
        />
      </div>
    ))}
  </div>
);

export default FormRenderer;
