/* eslint-disable react-refresh/only-export-components -- shares a plain
   helper (summarizeRow) alongside the RowList component on purpose. */

import { formatTimeDuration } from "@/pages/Profile/utils";

/**
 * Read-only rendering of one submitted education or experience row.
 *
 * @param {{institution?: string, title?: string, degree?: string,
 *          company?: string, field?: string, startMonth?: string,
 *          startYear?: string|number, endMonth?: string,
 *          endYear?: string|number, isCurrentlyWorking?: boolean}} row
 * @returns {{heading: string, subheading?: string, duration: string}}
 */
export const summarizeRow = (row) => ({
  heading: row.institution ?? row.title ?? "",
  subheading: row.institution
    ? [row.degree, row.field].filter(Boolean).join(", ")
    : row.company,
  duration: formatTimeDuration(
    row.startMonth,
    row.startYear,
    row.endMonth,
    row.endYear,
    row.isCurrentlyWorking,
  ),
});

/** Read-only list of education/experience rows, sharing one rendering shape. */
export const RowList = ({ title, rows }) => (
  <div className="space-y-2">
    <h2 className="text-sm font-medium text-slate-700">{title}</h2>
    {rows.length === 0 ? (
      <p className="text-sm text-slate-400">None provided.</p>
    ) : (
      <ul className="space-y-1">
        {rows.map((row, i) => {
          const s = summarizeRow(row);
          return (
            <li key={row.id ?? i} className="text-sm text-slate-700">
              {s.heading}
              {s.subheading && ` — ${s.subheading}`}
              {s.duration && ` (${s.duration})`}
            </li>
          );
        })}
      </ul>
    )}
  </div>
);
