import { Badge } from "@/components/ui/badge";
import { formatDateWithZone } from "@/utils/dateTime";

/**
 * How the caller's latest block request about this person ended, on the page
 * they raised it from, when it was rejected: a badge, and who rejected it and
 * why beneath, with the date on hover. Nothing for any other outcome -- an
 * approved one shows as the block itself, and a withdrawn or superseded one is
 * nothing the raiser needs telling.
 *
 * @param {{request: {status: string, decidedByName?: string|null,
 *            decidedAt?: string|null, decisionNote?: string|null}|null,
 *          tz: string}} props
 *   tz: the IANA zone the hover date is shown in.
 */
const RejectedBlockRequest = ({ request, tz }) => {
  if (request?.status !== "rejected") return null;
  const when = formatDateWithZone(request.decidedAt, tz);
  return (
    <div
      className="flex flex-col gap-1"
      title={when ? `Rejected ${when}` : undefined}
    >
      <Badge
        variant="outline"
        className="w-fit border-slate-300 bg-slate-100 text-slate-700"
      >
        Request rejected
      </Badge>
      <p className="text-xs text-slate-500">
        {request.decidedByName}: {request.decisionNote}
      </p>
    </div>
  );
};

export default RejectedBlockRequest;
