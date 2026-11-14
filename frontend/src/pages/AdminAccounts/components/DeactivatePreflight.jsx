import {
  formatDateTimeWithZone,
  resolveViewerTimezone,
} from "@/utils/dateTime";

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

/**
 * What stands in the way of deactivating an account, and what it leaves
 * alone.
 *
 * A mentorship round still holding the person blocks the deactivation: the
 * mentorship admins withdraw them first, or the operator waits until the round
 * is over. Open applications never block; they are listed so the operator can
 * tell the recruiter.
 *
 * `preflight` being null means it is still on its way.
 *
 * @param {{preflight: {mentorshipRounds: Array<{roundId: number, roundName: string, role: string|null, pairCount: number, withdrawPending: boolean, endsAt: string}>, openApplicationCount: number, interviewTimes: string[]}|null, timezone?: string, error?: boolean}} props
 * @param {object|null} props.preflight DeactivatePreflightDto, or null.
 * @param {string} [props.timezone] Zone to render times in; the browser's by
 *   default.
 * @param {boolean} [props.error] The pre-flight could not be read.
 * @returns {JSX.Element}
 */
const DeactivatePreflight = ({ preflight, timezone, error = false }) => {
  const tz = resolveViewerTimezone(timezone);
  const rounds = preflight?.mentorshipRounds ?? [];
  const openCount = preflight?.openApplicationCount ?? 0;
  const interviewTimes = preflight?.interviewTimes ?? [];

  const describeRound = (round) => {
    const details = [];
    if (round.role) details.push(round.role);
    if (round.pairCount) details.push(plural(round.pairCount, "pair", "pairs"));
    if (round.withdrawPending) details.push("withdrawal awaiting approval");
    details.push(`until ${formatDateTimeWithZone(round.endsAt, tz)}`);
    return `· ${round.roundName} — ${details.join(", ")}`;
  };

  const recruiting = () => {
    if (openCount === 0) return "· No open applications";
    const applications =
      openCount === 1 ? "1 open application" : `${openCount} open applications`;
    if (interviewTimes.length === 0) {
      return openCount === 1
        ? `· ${applications} stays as it is — tell the recruiter`
        : `· ${applications} stay as they are — tell the recruiter`;
    }
    const dates = interviewTimes
      .map((iso) => formatDateTimeWithZone(iso, tz))
      .filter(Boolean)
      .join(", ");
    return `· ${applications} and ${plural(
      interviewTimes.length,
      "upcoming interview",
      "upcoming interviews",
    )} (${dates}) stay as they are — tell the recruiter`;
  };

  if (preflight === null) {
    return (
      <div
        data-testid="deactivate-preflight"
        className="space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700"
      >
        {error ? (
          <p className="text-slate-500">
            Couldn&apos;t check what this account is still part of. Deactivating
            is refused if a mentorship round still holds them.
          </p>
        ) : (
          <p>· Checking what this account is still part of…</p>
        )}
      </div>
    );
  }

  const allPending = rounds.every((round) => round.withdrawPending);

  return (
    <div data-testid="deactivate-preflight" className="space-y-2 text-sm">
      {rounds.length > 0 ? (
        <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900">
          <p className="font-medium">
            Still in mentorship — cannot be deactivated yet
          </p>
          <ul className="space-y-1">
            {rounds.map((round) => (
              <li key={round.roundId}>{describeRound(round)}</li>
            ))}
          </ul>
          <p>
            {allPending
              ? "Wait for the withdrawal to be decided, or deactivate once those dates have passed."
              : "Ask the mentorship admins to withdraw them, or deactivate once those dates have passed."}
          </p>
        </div>
      ) : null}
      <ul className="space-y-1 rounded-md border border-slate-200 bg-slate-50 p-3 text-slate-700">
        {rounds.length === 0 && (
          <li>· Not in any mentorship round in progress</li>
        )}
        <li>{recruiting()}</li>
      </ul>
    </div>
  );
};

export default DeactivatePreflight;
