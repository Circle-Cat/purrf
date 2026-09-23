/**
 * PairCell
 *
 * A person's current pairs, inside their own row — there is no separate pair
 * table. A mentee has at most one active pair a round, so their row carries
 * that pair's facts, first contact included: it is the mentee who reaches out,
 * and marking it is marking them. A mentor can carry several mentees and gets
 * one line per pair, still in one row. Ended pairs are not listed; they stay
 * on the person's page and the pair's own page.
 *
 * First contact is kept on the pair rather than the person so that a mentee
 * who changes partner starts again at "not yet" with the new mentor.
 *
 * @param {{person: object, pairs: object[], writable: boolean, onOpenPair: (pairId: number) => void, onMarkFirstContact: (pairId: number) => void}} props
 * @returns {JSX.Element}
 */
const PairCell = ({
  person,
  pairs,
  writable,
  onOpenPair,
  onMarkFirstContact,
}) => {
  const mine = pairs.filter(
    (p) =>
      p.status === "active" &&
      (p.mentorId === person.userId || p.menteeId === person.userId),
  );
  if (mine.length === 0) return <span className="text-slate-400">—</span>;

  return (
    <ul className="space-y-1">
      {mine.map((pair) => {
        const isMentee = pair.menteeId === person.userId;
        const partner = isMentee ? pair.mentorName : pair.menteeName;
        const contacted = pair.firstContactConfirmedAt;
        return (
          <li
            key={pair.pairId}
            className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs"
          >
            <button
              type="button"
              aria-label={`Open pair ${pair.mentorName} and ${pair.menteeName}`}
              onClick={() => onOpenPair(pair.pairId)}
              className="font-medium text-slate-800 underline-offset-2 hover:underline"
            >
              with {partner}
            </button>
            <span className="text-slate-500">
              Meetings {pair.completed}/{pair.required}
            </span>
            {isMentee ? (
              <button
                type="button"
                aria-label={
                  contacted
                    ? `First contact confirmed ${contacted} — ${person.name}`
                    : `Mark first contact — ${person.name}`
                }
                disabled={!writable}
                onClick={() => onMarkFirstContact(pair.pairId)}
                className={`rounded px-1.5 py-0.5 ${
                  contacted
                    ? "bg-emerald-100 text-emerald-800"
                    : "border border-slate-300 text-slate-500 hover:bg-slate-100"
                } ${writable ? "" : "cursor-default opacity-60"}`}
              >
                {contacted
                  ? `First contact ✓ ${contacted}`
                  : "First contact — mark"}
              </button>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
};

export default PairCell;
