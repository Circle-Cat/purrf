import { ArrowLeft } from "lucide-react";
import { Card } from "@/components/ui/card";
import { ENTRY_LABEL } from "@/pages/LeavePrototype/leaveCalc";

/**
 * LedgerPage
 *
 * Every change to the balance, newest first, footed with the total so the
 * arithmetic can be checked by eye.
 *
 * This exists because the dashboard card shows three figures and deliberately
 * does not explain how they got there. Accrual, carry-over and corrections all
 * land here instead of cluttering the summary.
 *
 * @param {object} props
 * @param {Array<object>} props.ledger
 * @param {number} props.balance
 * @param {number} props.pending - hours held by requests awaiting a decision
 * @param {number} props.available
 * @param {() => void} props.onBack
 * @returns {JSX.Element}
 */
const LedgerPage = ({ ledger, balance, pending, available, onBack }) => {
  const history = [...ledger].sort((a, b) =>
    a.effectiveDate === b.effectiveDate
      ? b.id - a.id
      : b.effectiveDate.localeCompare(a.effectiveDate),
  );

  return (
    <div className="p-6 space-y-4 max-w-4xl">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 transition-colors"
      >
        <ArrowLeft size={15} />
        Back to dashboard
      </button>

      <header>
        <h1 className="text-xl font-semibold text-slate-900">
          Balance history
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Entries are only ever added — a correction is a new line, never an
          edit to an old one.
        </p>
      </header>

      <Card className="p-5">
        <ul className="divide-y divide-slate-100">
          {history.map((row) => (
            <li
              key={row.id}
              className="py-2.5 flex items-baseline justify-between gap-4"
            >
              <div className="min-w-0">
                <span className="text-sm text-slate-800">
                  {ENTRY_LABEL[row.entryType] ?? row.entryType}
                </span>
                {row.note && (
                  <p className="text-xs text-slate-400 mt-0.5">{row.note}</p>
                )}
              </div>
              <div className="shrink-0 text-right">
                <span
                  className={`text-sm font-medium tabular-nums ${
                    row.hours < 0 ? "text-rose-600" : "text-emerald-700"
                  }`}
                >
                  {row.hours > 0 ? "+" : ""}
                  {row.hours.toFixed(2)}h
                </span>
                <p className="text-xs text-slate-400 tabular-nums">
                  {row.effectiveDate}
                </p>
              </div>
            </li>
          ))}
        </ul>

        {/* Foots the list, and reconciles it with the Available figure on the
            dashboard card — otherwise there are two totals and no way to tell
            which one is the real balance. */}
        <div className="mt-3 pt-3 border-t border-slate-200 space-y-1">
          <div className="flex items-baseline justify-between">
            <span className="text-sm font-medium text-slate-900">
              Total on record
            </span>
            <span className="text-sm font-semibold tabular-nums text-slate-900">
              {balance.toFixed(2)}h
            </span>
          </div>
          {pending > 0 && (
            <>
              <div className="flex items-baseline justify-between text-slate-500">
                <span className="text-sm">Less held by pending requests</span>
                <span className="text-sm tabular-nums">
                  −{pending.toFixed(2)}h
                </span>
              </div>
              <div className="flex items-baseline justify-between pt-1">
                <span className="text-sm font-medium text-slate-900">
                  Available to request
                </span>
                <span className="text-sm font-semibold tabular-nums text-slate-900">
                  {available.toFixed(2)}h
                </span>
              </div>
            </>
          )}
        </div>
      </Card>
    </div>
  );
};

export default LedgerPage;
