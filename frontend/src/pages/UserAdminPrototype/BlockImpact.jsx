import { AlertTriangle } from "lucide-react";

/**
 * BlockImpact
 *
 * The pre-flight shown before a block is requested or applied.
 *
 * Counts and dates, never titles. The approver needs to know how large the
 * consequence is and how soon it lands; which posting someone applied to is
 * not part of that, and who applied to what is not an operator's business.
 * The one identity that does appear is the mentorship partner, because ending
 * the pair costs *them* a partner mid-round — they are an affected party, so
 * the person deciding is entitled to know who they are about to affect.
 *
 * @param {{impact: object}} props
 * @returns {JSX.Element}
 */
const BlockImpact = ({ impact }) => {
  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

  return (
    <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
      <div>
        <p className="font-medium text-slate-900">Applying this will</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-slate-700">
          <li>Lock the person out of all of Purrf until unblocked</li>
          <li>
            Reject and tag {plural(impact.applications, "application")},
            including any already hired
          </li>
          {impact.interviews.length > 0 ? (
            <li>
              Cancel {plural(impact.interviews.length, "interview")} —{" "}
              {impact.interviews.join(", ")}
            </li>
          ) : (
            <li>Cancel no interviews — none are scheduled</li>
          )}
          {impact.pairs.length > 0 ? (
            <li>
              End {plural(impact.pairs.length, "mentorship pair")} mid-round,
              leaving {impact.pairs.join(" and ")} without a partner
            </li>
          ) : (
            <li>End no mentorship pair — this person is not paired</li>
          )}
          {impact.mentorshipMeetings.length > 0 ? (
            <li>
              Cancel{" "}
              {plural(impact.mentorshipMeetings.length, "mentorship meeting")}{" "}
              that has not happened yet — {impact.mentorshipMeetings.join(", ")}
            </li>
          ) : (
            <li>Cancel no mentorship meeting — none are scheduled</li>
          )}
        </ul>
      </div>

      <div className="flex gap-2 rounded-md border border-amber-300 bg-amber-50 p-2">
        <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-700" />
        <p className="text-amber-900">
          Unblocking later restores access, but reinstates none of the above —
          not the applications, not the interviews, not the pair. Mentorship
          eligibility is gone for good, because it is derived from an
          application that this action rejects. Treat it as permanent.
        </p>
      </div>
    </div>
  );
};

export default BlockImpact;
