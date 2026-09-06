/**
 * The account-state chips for one person.
 *
 * The three states are orthogonal, not a single status column: the same
 * account can be blocked and deactivated at once, and a block request is a
 * fact about a person who is still fully active. All three are drawn side by
 * side so nothing is hidden behind a winner-takes-all label.
 *
 * Tailwind v4 note: a bare `border` is currentColor, so every chip names its
 * own border colour.
 *
 * @param {Object} props
 * @param {boolean} props.isActive
 * @param {boolean} props.isBlocked
 * @param {boolean} props.hasPendingBlockRequest - Scoped by the backend to the
 *   caller: true only when a pending request names them as its reviewer.
 */
const StateChips = ({ isActive, isBlocked, hasPendingBlockRequest }) => {
  const base =
    "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium";

  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {isBlocked && (
        <span className={`${base} border-red-300 bg-red-50 text-red-700`}>
          Blocked
        </span>
      )}
      {!isActive && (
        <span
          className={`${base} border-slate-300 bg-slate-100 text-slate-700`}
        >
          Deactivated
        </span>
      )}
      {hasPendingBlockRequest && (
        <span className={`${base} border-amber-300 bg-amber-50 text-amber-800`}>
          Block requested
        </span>
      )}
      {isActive && !isBlocked && (
        // Shown even alongside "Block requested". A pending request is a fact
        // about someone who is still fully active, and hiding Active while one
        // is open would read as if their access were already in doubt.
        <span
          className={`${base} border-emerald-300 bg-emerald-50 text-emerald-700`}
        >
          Active
        </span>
      )}
    </span>
  );
};

export default StateChips;
