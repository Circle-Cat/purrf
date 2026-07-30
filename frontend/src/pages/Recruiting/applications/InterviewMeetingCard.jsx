import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatInTz } from "@/utils/dateTime";

/**
 * The scheduled interview meeting for one application's current stage+round.
 *
 * Renders five states: not scheduled, booked, booked-but-past, a round label
 * past the first, and a warning when the application reached a terminal
 * stage with the meeting still on the calendar.
 *
 * The booked time is rendered in `timezone` -- the VIEWER's own zone, not the
 * zone whoever booked it happened to be in (nothing stores that) -- printed
 * verbatim as its IANA name, e.g. "2026-08-05 · 14:00 - 14:45
 * America/Los_Angeles". The zone name is never omitted: two people in
 * different zones read this same card, and a bare "14:00" would look right to
 * both of them while meaning different moments. No `PDT`/`PST` abbreviation is
 * derived either -- the IANA name is unambiguous on its own, and a derived
 * abbreviation risks silently disagreeing with it around a DST transition.
 *
 * A `read.all` viewer who isn't the owner (`isOwner={false}`) sees the exact
 * same state -- the booked time/link/labels, or "Not scheduled" -- but none
 * of the action buttons: no "Schedule meeting", no "Edit", no "Cancel". This
 * mirrors how the rest of the detail page treats a read.all viewer (see
 * `canReassign`/`detail.isOwner` on `ApplicationDetailPage`): the same
 * information, none of the controls.
 *
 * @param {{interview: object|null, round: number, timezone: string,
 *          isTerminal?: boolean, isOwner?: boolean, busy?: boolean,
 *          onSchedule?: function, onEdit?: function, onCancel?: function}} props
 */
const InterviewMeetingCard = ({
  interview,
  round,
  timezone,
  isTerminal = false,
  isOwner = true,
  busy = false,
  onSchedule,
  onEdit,
  onCancel,
}) => {
  if (!interview) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Interview Meeting</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-slate-500">Not scheduled</p>
          {isOwner && (
            <Button
              type="button"
              size="sm"
              disabled={busy}
              onClick={() => onSchedule?.()}
            >
              Schedule meeting
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const isPast = new Date(interview.endAt).getTime() < Date.now();
  const meetLinkDisplay = interview.meetLink
    ? interview.meetLink.replace(/^https?:\/\//, "")
    : null;
  const timeRange = `${formatInTz(interview.startAt, timezone, "yyyy-MM-dd")} · ${formatInTz(
    interview.startAt,
    timezone,
    "HH:mm",
  )} - ${formatInTz(interview.endAt, timezone, "HH:mm")} ${timezone}`;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>Interview Meeting</CardTitle>
          {round > 1 && <Badge variant="secondary">{`Round ${round}`}</Badge>}
          {isPast && <Badge variant="outline">Past</Badge>}
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-sm text-slate-700">{timeRange}</p>
        {meetLinkDisplay && (
          <a
            href={interview.meetLink}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-blue-600 underline"
          >
            {meetLinkDisplay}
          </a>
        )}
        <p className="text-xs text-slate-500">
          Interviewer: {interview.assigneeName ?? "Unassigned"}. Scheduled by{" "}
          {interview.scheduledByName ?? "—"}.
        </p>
        {isTerminal && (
          <p className="text-sm text-amber-600">
            This application has already reached a terminal stage, but the
            meeting is still on the calendar.
          </p>
        )}
      </CardContent>
      {isOwner && (
        <div className="flex flex-wrap items-center gap-2 px-6">
          {!isTerminal && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => onEdit?.()}
            >
              Edit
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => onCancel?.()}
          >
            Cancel
          </Button>
        </div>
      )}
    </Card>
  );
};

export default InterviewMeetingCard;
