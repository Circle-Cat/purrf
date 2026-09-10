import { Fragment } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import UserAssignmentsRow from "@/pages/AdminTraining/components/UserAssignmentsRow";
import { useUserAssignments } from "@/pages/AdminTraining/hooks/useUserAssignments";
import {
  courseStatusLabel,
  coursesHeldLabel,
} from "@/pages/AdminTraining/utils";

const COLUMN_COUNT = 7;

/** What to call somebody in the table and in a checkbox's label. */
const personName = ({ preferredName, firstName, lastName }) =>
  preferredName || [firstName, lastName].filter(Boolean).join(" ") || "Unnamed";

/**
 * The result table for the audience search: one row per person, a checkbox
 * that survives paging, one column that answers either the course in scope or
 * the person's whole training list, and a row that expands into every course
 * they hold.
 *
 * The expansion is read-only and independent of the target course. It is the
 * only place in the repo where an administrator can see somebody else's
 * training list.
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
  const { expandedUserId, rowsByUserId, loadingUserId, toggle } =
    useUserAssignments();
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
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                <span className="sr-only">Courses held</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const expanded = expandedUserId === row.userId;
              return (
                <Fragment key={row.userId}>
                  <tr data-testid={`audience-row-${row.userId}`}>
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
                    <td className="border-b border-slate-200 px-4 py-3">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-expanded={expanded}
                        aria-label={`${expanded ? "Hide" : "Show"} courses for ${personName(row)}`}
                        onClick={() => toggle(row.userId)}
                      >
                        {expanded ? (
                          <ChevronDown className="size-4" />
                        ) : (
                          <ChevronRight className="size-4" />
                        )}
                      </Button>
                    </td>
                  </tr>
                  {expanded && (
                    <UserAssignmentsRow
                      userId={row.userId}
                      columnCount={COLUMN_COUNT}
                      loading={loadingUserId === row.userId}
                      rows={rowsByUserId[row.userId]}
                    />
                  )}
                </Fragment>
              );
            })}
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
