/**
 * One recorded answer's value, rendered from its actual runtime shape rather
 * than from a question type.
 *
 * A recorded value and the question it is filed under can disagree: a job's
 * `form_schema` is overwritten in place on every posting edit, so an answer
 * recorded as an array can end up under a question that is now `short_text`
 * (and vice versa), and an orphaned answer has no question left to consult at
 * all. Rendering from the value's own shape is what keeps such an answer on
 * the page instead of silently collapsing it to "Not answered".
 *
 * Text is rendered as a `whitespace-pre-wrap` block rather than a filled-in
 * control: a single-line `<Input>` visually truncates a long answer and a
 * `<Textarea>` buries a multi-paragraph one behind an inner scrollbar, both of
 * which defeat the point of reviewing the answer.
 *
 * @param {{value: unknown}} props
 */
export const RecordedValue = ({ value }) => {
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc pl-5 text-sm text-slate-700">
        {value.map((item, i) => (
          <li key={`${String(item)}-${i}`}>{String(item)}</li>
        ))}
      </ul>
    );
  }
  if (value !== null && typeof value === "object") {
    return (
      <pre className="overflow-x-auto text-xs text-slate-700">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  const text = value == null ? "" : String(value);
  return text.trim() === "" ? (
    <p className="text-sm text-slate-400">Not answered</p>
  ) : (
    <p className="whitespace-pre-wrap text-sm text-slate-700">{text}</p>
  );
};
