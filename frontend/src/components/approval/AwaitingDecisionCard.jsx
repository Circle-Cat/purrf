/**
 * One request waiting on the viewer's decision, at the top of the page it is
 * about: what is asked, who asked and when, why, and the decision buttons.
 * Every kind of approval shows it the same way.
 *
 * @param {object} props
 * @param {string} props.title What waits, e.g. "Red flag awaiting your
 *   decision"; also the region's name.
 * @param {(string|null|undefined)[]} props.meta Lines under the title; empty
 *   ones are left out.
 * @param {string|null} [props.reason] The asker's reason, shown as written.
 * @param {string} [props.emptyReason] Said instead when there is none.
 * @param {import("react").ReactNode} [props.children] The decision buttons.
 */
const AwaitingDecisionCard = ({
  title,
  meta,
  reason,
  emptyReason = "No reason given.",
  children,
}) => (
  <section
    aria-label={title}
    className="rounded-lg border border-amber-300 bg-amber-50 p-4"
  >
    <h2 className="text-sm font-bold uppercase tracking-wide text-amber-900">
      {title}
    </h2>
    {meta.filter(Boolean).map((line) => (
      <p key={line} className="mt-1 text-sm text-amber-900">
        {line}
      </p>
    ))}
    {reason ? (
      <p className="mt-3 whitespace-pre-wrap text-sm text-slate-900">
        {reason}
      </p>
    ) : (
      <p className="mt-3 text-sm text-slate-500">{emptyReason}</p>
    )}
    {children && <div className="mt-4 flex gap-2">{children}</div>}
  </section>
);

export default AwaitingDecisionCard;
