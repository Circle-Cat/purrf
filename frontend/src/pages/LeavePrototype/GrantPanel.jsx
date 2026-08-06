import { useState } from "react";
import { AlertTriangle, Gift } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { REGIONS } from "@/pages/LeavePrototype/mockData";

/**
 * GrantPanel
 *
 * Hands out the half of the extra paid leave that is not accrued weekly, to
 * everyone in a region at once, ahead of a public holiday.
 *
 * It is manual because nothing in this system knows when public holidays fall
 * — the statutory calendar was dropped once it stopped driving accrual. So the
 * only guard against giving out the wrong amount over a year is showing what
 * is left, which is what the bar is for.
 *
 * @param {object} props
 * @param {string} props.region
 * @param {number} props.allowance - the region's annual granted figure
 * @param {Array<object>} props.grants - grants already issued this year
 * @param {number} props.headcount - how many people a grant would reach
 * @param {(grant: object) => void} props.onGrant
 * @returns {JSX.Element}
 */
const GrantPanel = ({ region, allowance, grants, headcount, onGrant }) => {
  const [hours, setHours] = useState("8");
  const [reason, setReason] = useState("");

  const issued = grants.reduce((n, g) => n + g.hours, 0);
  const remaining = Math.round((allowance - issued) * 100) / 100;

  const parsed = Number(hours);
  const valid = hours !== "" && !Number.isNaN(parsed) && parsed > 0;
  const wouldOverrun = valid && parsed > remaining;
  const canGrant = valid && reason.trim().length > 0 && allowance > 0;

  const submit = () => {
    if (!canGrant) return;
    onGrant({
      id: Date.now(),
      region,
      hours: parsed,
      reason: reason.trim(),
      headcount,
    });
    setHours("8");
    setReason("");
  };

  const pct = allowance > 0 ? Math.min(100, (issued / allowance) * 100) : 0;

  return (
    <div className="space-y-4">
      <Card className="p-5 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Grant extra leave to {REGIONS[region].label}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Writes one ledger row for every employee in the region, dated
              today. Issue it before the holiday it is meant to cover.
            </p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-xs uppercase tracking-wide text-slate-500">
              Left this year
            </p>
            <p
              className={`text-2xl font-semibold tabular-nums ${
                remaining < 0 ? "text-rose-600" : "text-slate-900"
              }`}
            >
              {remaining.toFixed(2)}h
            </p>
            <p className="text-xs text-slate-400 tabular-nums">
              of {allowance.toFixed(2)}h
            </p>
          </div>
        </div>

        {allowance > 0 && (
          <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
            <div
              className={`h-full ${remaining < 0 ? "bg-rose-500" : "bg-slate-700"}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        )}

        {allowance === 0 ? (
          <p className="text-sm text-slate-500">
            {REGIONS[region].label} grants none of its extra leave this way — it
            all accrues weekly. Nothing to issue.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-end gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="grant-hours" className="text-xs">
                  Hours each
                </Label>
                <Input
                  id="grant-hours"
                  type="number"
                  step="4"
                  className="w-28"
                  value={hours}
                  onChange={(e) => setHours(e.target.value)}
                />
              </div>
              <div className="space-y-1.5 flex-1 min-w-48">
                <Label htmlFor="grant-reason" className="text-xs">
                  What it is for
                </Label>
                <Input
                  id="grant-reason"
                  value={reason}
                  placeholder="Spring Festival"
                  onChange={(e) => setReason(e.target.value)}
                />
              </div>
              <Button onClick={submit} disabled={!canGrant} className="h-9">
                <Gift size={15} />
                Grant to {headcount}
              </Button>
            </div>

            {wouldOverrun && (
              <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900">
                <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                <p>
                  Only {remaining.toFixed(2)}h left of this year&apos;s{" "}
                  {allowance.toFixed(2)}h. Granting {parsed}h takes the region
                  over. Allowed — you may have a reason — but it will show as a
                  negative balance here.
                </p>
              </div>
            )}
          </>
        )}
      </Card>

      {grants.length > 0 && (
        <Card className="p-5">
          <h3 className="text-sm font-semibold text-slate-900 mb-3">
            Granted this year
          </h3>
          <ul className="divide-y divide-slate-100">
            {grants.map((g) => (
              <li
                key={g.id}
                className="py-2.5 flex items-center justify-between gap-4 text-sm"
              >
                <div className="min-w-0">
                  <span className="text-slate-800">{g.reason}</span>
                  <span className="text-xs text-slate-400 ml-2">
                    {g.headcount} people
                  </span>
                </div>
                <span className="tabular-nums font-medium text-emerald-700 shrink-0">
                  +{g.hours.toFixed(2)}h each
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
};

export default GrantPanel;
