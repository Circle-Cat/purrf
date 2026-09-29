import { ENTRY_LABEL } from "@/pages/LeavePrototype/leaveCalc";

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/**
 * `2026-10-01` -> `Oct 1, 2026`, by splitting the string. A leave date is one
 * calendar day for the whole company; building a Date from it would render
 * the day before for anybody west of UTC.
 *
 * @param {string} iso
 * @returns {string}
 */
const formatDay = (iso) => {
  const [year, month, day] = iso.split("-");
  return `${MONTHS[Number(month) - 1]} ${Number(day)}, ${year}`;
};

/**
 * LedgerRow
 *
 * One ledger entry, the same on the employee's Balance history and the
 * administrator's Ledger tab: what it was and why on the left, the hours and
 * the day on the right.
 *
 * The administrator's list covers everybody, so it passes `person` and the
 * row names whose entry it is above the type. An account that no longer
 * resolves is still named by its id rather than left blank.
 *
 * @param {object} props
 * @param {{entryType: string, hours: number, effectiveDate: string, note?: string|null}} props.row
 * @param {{userId: number, name: string|null, ldap: string|null}} [props.person]
 * @returns {JSX.Element}
 */
const LedgerRow = ({ row, person }) => (
  <li className="py-2.5 flex items-baseline justify-between gap-4">
    <div className="min-w-0">
      {person && (
        <p className="text-xs text-slate-500 mb-0.5">
          <span className="font-medium text-slate-700">
            {person.name ?? `User ${person.userId} — unavailable`}
          </span>
          {person.ldap && <span> · {person.ldap}</span>}
        </p>
      )}
      <span className="text-sm text-slate-800">
        {ENTRY_LABEL[row.entryType] ?? row.entryType}
      </span>
      {row.note && <p className="text-xs text-slate-400 mt-0.5">{row.note}</p>}
    </div>
    <div className="shrink-0 text-right">
      <span
        className={`text-sm font-medium tabular-nums ${
          row.hours < 0
            ? "text-rose-600"
            : row.hours > 0
              ? "text-emerald-700"
              : "text-slate-500"
        }`}
      >
        {row.hours > 0 ? "+" : ""}
        {row.hours.toFixed(2)}h
      </span>
      <p className="text-xs text-slate-400 tabular-nums">
        {formatDay(row.effectiveDate)}
      </p>
    </div>
  </li>
);

export default LedgerRow;
