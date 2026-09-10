import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import {
  courseStatusLabel,
  coursesHeldLabel,
} from "@/pages/AdminTraining/utils";

/** What to call somebody in the table and in a checkbox's label. */
const personName = ({ preferredName, firstName, lastName }) =>
  preferredName || [firstName, lastName].filter(Boolean).join(" ") || "Unnamed";

/**
 * The result table for the audience search: one row per person, a checkbox
 * that survives paging, and one column that answers either the course in
 * scope or the person's whole training list.
 *
 * @param {Object} props
 * @param {Array<Object>} props.rows `TrainingAudienceRowDto` rows.
 * @param {boolean} props.courseScoped whether a course is in scope, which
 *   decides what the last column can answer.
 * @param {Array<number>} props.selectedIds ticked ids, across pages.
 * @param {(userId: number, checked: boolean) => void} props.onToggle
 * @param {(checked: boolean) => void} props.onTogglePage ticks or unticks
 *   everyone on this page only.
 * @param {number} props.total matches across all pages.
 * @param {number} props.limit page size.
 * @param {number} props.offset rows skipped.
 * @param {() => void} props.onPrev
 * @param {() => void} props.onNext
 */
export default function AudienceTable({
  rows,
  courseScoped,
  selectedIds,
  onToggle,
  onTogglePage,
  total,
  limit,
  offset,
  onPrev,
  onNext,
}) {
  const selected = new Set(selectedIds);
  const pageAllTicked =
    rows.length > 0 && rows.every((row) => selected.has(row.userId));

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-auto rounded-lg border border-slate-200">
        <table className="w-full min-w-fit border-collapse text-sm leading-normal">
          <thead>
            <tr>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                <Checkbox
                  checked={pageAllTicked}
                  onCheckedChange={(checked) => onTogglePage(checked === true)}
                  aria-label="Select everyone on this page"
                />
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                Name
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                Email
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                User ID
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                Type
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                {courseScoped ? "On this course" : "Courses"}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.userId} data-testid={`audience-row-${row.userId}`}>
                <td className="border-b border-slate-200 px-4 py-3">
                  <Checkbox
                    checked={selected.has(row.userId)}
                    onCheckedChange={(checked) =>
                      onToggle(row.userId, checked === true)
                    }
                    aria-label={`Select ${personName(row)}`}
                  />
                </td>
                <td className="border-b border-slate-200 px-4 py-3">
                  {personName(row)}
                </td>
                <td className="border-b border-slate-200 px-4 py-3">
                  {row.contactEmail ?? "—"}
                </td>
                <td className="border-b border-slate-200 px-4 py-3">
                  {row.userId}
                </td>
                <td className="border-b border-slate-200 px-4 py-3">
                  {row.isInternal ? "Internal" : "External"}
                </td>
                <td className="border-b border-slate-200 px-4 py-3">
                  {courseScoped
                    ? courseStatusLabel(row.courseStatus)
                    : coursesHeldLabel(row)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
        <Button
          variant="outline"
          size="sm"
          onClick={onPrev}
          disabled={offset === 0}
        >
          Prev
        </Button>
        <span>
          {total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)} of{" "}
          {total}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={onNext}
          disabled={offset + limit >= total}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
