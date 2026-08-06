import { CalendarDays, History, ListChecks, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/**
 * One figure in the card header.
 *
 * @param {{label: string, value: string, hint?: string, tone?: string}} props
 * @returns {JSX.Element}
 */
const Stat = ({ label, value, hint, tone = "text-slate-900" }) => (
  <div className="min-w-0">
    <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
    <p className={`text-2xl font-semibold tabular-nums mt-1 ${tone}`}>
      {value}
    </p>
    {hint && <p className="text-xs text-slate-400 mt-0.5">{hint}</p>}
  </div>
);

/**
 * TimeOffCard
 *
 * The leave module's whole presence on the personal dashboard: three figures
 * answering "what can I spend", and the four things anyone comes here to do.
 *
 * The card itself never grows — requesting and the holiday list open in
 * dialogs, and the two histories are pages of their own, because a dashboard
 * card that expands into a long list stops being a dashboard card.
 *
 * @param {object} props
 * @param {number} props.available
 * @param {number} props.pending - hours held by requests awaiting a decision
 * @param {number} props.used
 * @param {number} props.pendingCount
 * @param {() => void} props.onRequest
 * @param {() => void} props.onViewHolidays
 * @param {() => void} props.onViewRequests
 * @param {() => void} props.onViewLedger
 * @returns {JSX.Element}
 */
const TimeOffCard = ({
  available,
  pending,
  used,
  pendingCount,
  onRequest,
  onViewHolidays,
  onViewRequests,
  onViewLedger,
}) => (
  <Card className="p-5 space-y-5">
    <div className="flex items-start justify-between gap-4">
      <h2 className="text-sm font-semibold text-slate-900">Time off</h2>
      {pendingCount > 0 && (
        <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">
          {pendingCount} awaiting a decision
        </span>
      )}
    </div>

    <div className="grid grid-cols-3 gap-6">
      <Stat
        label="Available"
        value={`${available.toFixed(2)}h`}
        hint={`${(available / 8).toFixed(1)} days`}
        tone={available < 0 ? "text-rose-600" : "text-slate-900"}
      />
      <Stat
        label="Pending"
        value={`${pending.toFixed(2)}h`}
        hint="Requested, not yet decided"
      />
      <Stat
        label="Used"
        value={`${used.toFixed(2)}h`}
        hint="Approved and taken"
      />
    </div>

    <div className="flex flex-wrap gap-2 pt-1">
      <Button size="sm" onClick={onRequest}>
        <Plus size={15} />
        Request time off
      </Button>
      <Button size="sm" variant="outline" onClick={onViewHolidays}>
        <CalendarDays size={15} />
        Company holidays
      </Button>
      <Button size="sm" variant="outline" onClick={onViewRequests}>
        <ListChecks size={15} />
        My requests
      </Button>
      <Button size="sm" variant="outline" onClick={onViewLedger}>
        <History size={15} />
        Balance history
      </Button>
    </div>
  </Card>
);

export default TimeOffCard;
