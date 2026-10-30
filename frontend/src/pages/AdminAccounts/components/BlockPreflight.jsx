import {
  formatDateTimeWithZone,
  resolveViewerTimezone,
} from "@/utils/dateTime";

/**
 * What blocking this person is about to do, stated before it happens.
 *
 * Word-for-word the same block in both modes of `BlockDialog`: a reviewer
 * deciding a request has to read exactly what the raiser read, or the two are
 * agreeing to different things.
 *
 * Also shown to the reviewer approving a block request, for the same reason.
 *
 * `preflight` being null means the counts are still on their way. The warning
 * about irreversibility is not conditional on them: it is true regardless of
 * how many rows the sweep turns out to reach.
 *
 * @param {{preflight: {applicationCount: number, interviewTimes: string[], mentorshipPairCount?: number, mentorshipMeetingCount?: number}|null, timezone?: string, error?: boolean}} props
 * @param {{applicationCount: number, interviewTimes: string[], mentorshipPairCount?: number, mentorshipMeetingCount?: number}|null} props.preflight
 *   Counts and dates from the preflight endpoint, or null while it is loading
 *   or could not be read.
 * @param {string} [props.timezone] Zone to render the interview times in.
 *   Defaults to the browser's. The recruiting page renders every other time
 *   from the viewer's profile zone, so it passes that in rather than letting
 *   one block on the page disagree with the rest.
 * @param {boolean} [props.error] The preflight could not be read. Stated
 *   under the block, not fatal: the counts are context for a decision, not a
 *   precondition for taking it.
 * @returns {JSX.Element}
 */
const BlockPreflight = ({ preflight, timezone, error = false }) => {
  const tz = resolveViewerTimezone(timezone);
  const applicationCount = preflight?.applicationCount ?? 0;
  const interviewTimes = preflight?.interviewTimes ?? [];
  const pairCount = preflight?.mentorshipPairCount ?? 0;
  const meetingCount = preflight?.mentorshipMeetingCount ?? 0;
  const dates = interviewTimes
    .map((iso) => formatDateTimeWithZone(iso, tz))
    .filter(Boolean)
    .join(", ");

  return (
    <>
      <div
        data-testid="block-preflight"
        className="space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700"
      >
        <p>Applying this will</p>
        <ul className="space-y-1">
          <li>· Lock the person out of all of Purrf until unblocked</li>
          {preflight === null ? (
            <li>
              · Still counting the applications, interviews and mentorship pairs
              this reaches
            </li>
          ) : (
            <>
              {/* The sweep tags every application it touches but only rejects
                the ones not already rejected, so the count cannot be phrased
                as a promise that all of them get closed out. */}
              <li>
                {`· Tag ${applicationCount} affected ${
                  applicationCount === 1 ? "application" : "applications"
                }, including any already hired, and reject every one that is not already rejected`}
              </li>
              <li>
                {interviewTimes.length === 0
                  ? "· Cancel no interviews — none are scheduled"
                  : `· Cancel ${interviewTimes.length} ${
                      interviewTimes.length === 1 ? "interview" : "interviews"
                    } — ${dates}`}
              </li>
              <li>
                {pairCount === 0
                  ? "· End no mentorship pairs — none in a round in progress"
                  : `· End ${pairCount} mentorship ${
                      pairCount === 1 ? "pair" : "pairs"
                    } in rounds in progress and cancel ${meetingCount} upcoming ${
                      meetingCount === 1 ? "meeting" : "meetings"
                    }; a partner left with no pair becomes unmatched`}
              </li>
            </>
          )}
        </ul>
        <p>
          ⚠ Unblocking later restores access, but reinstates none of the above —
          not the applications, not the interviews, not the mentorship pairs.
          Mentorship eligibility is gone for good, because it is derived from an
          application that this action rejects.
        </p>
      </div>
      {error && (
        <p className="text-sm text-slate-500">
          Couldn&apos;t read what this will affect. The block still does all of
          the above.
        </p>
      )}
    </>
  );
};

export default BlockPreflight;
