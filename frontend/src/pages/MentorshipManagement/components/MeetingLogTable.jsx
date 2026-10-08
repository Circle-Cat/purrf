// frontend/src/pages/MentorshipManagement/components/MeetingLogTable.jsx
import { ChevronDown, Pencil, Trash2 } from "lucide-react";
import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { formatInTz } from "@/utils/dateTime";
import { MEETING_TIMEZONE } from "@/pages/MentorshipManagement/utils/attendanceIssues";
import { getMeetingStatus } from "@/utils/meetingStatusCalculator";
import { MeetingStatus } from "@/constants/MeetingStatus";
import { MEETING_NOTE_TAGS } from "@/constants/MeetingNoteTags";
import {
  getDisabledNoteTags,
  hasAbsentTag,
  noteTagLabel,
} from "@/pages/MentorshipManagement/utils/meetingNoteTags";

/**
 * Formats a UTC meeting start/end datetime as a Pacific Time date + time range
 * string, e.g. "2026-04-06 · 15:30 - 16:30".
 *
 * @param {string} startDatetime - UTC ISO-8601 start datetime.
 * @param {string} endDatetime - UTC ISO-8601 end datetime.
 * @returns {string} Formatted Pacific Time date + time range.
 */
function formatMeetingTimeRange(startDatetime, endDatetime) {
  const date = formatInTz(startDatetime, MEETING_TIMEZONE, "yyyy-MM-dd");
  const start = formatInTz(startDatetime, MEETING_TIMEZONE, "HH:mm");
  const end = formatInTz(endDatetime, MEETING_TIMEZONE, "HH:mm");
  return `${date} · ${start} - ${end}`;
}

/**
 * Formats a UTC create datetime as a Pacific Time date + time, e.g. "2026-04-06 · 15:30".
 *
 * @param {string} createDatetime - UTC ISO-8601 create datetime.
 * @returns {string} Formatted Pacific Time date + time.
 */
function formatCreateDatetime(createDatetime) {
  const date = formatInTz(createDatetime, MEETING_TIMEZONE, "yyyy-MM-dd");
  const time = formatInTz(createDatetime, MEETING_TIMEZONE, "HH:mm");
  return `${date} · ${time}`;
}

/**
 * Renders a meeting's completion status. A not-yet-completed meeting whose
 * start time is still in the future is unambiguously "Scheduled" rather than
 * "Incomplete".
 *
 * @param {{isCompleted: boolean, startDatetime: string}} props
 */
function MeetingStatusCell({ isCompleted, startDatetime }) {
  switch (getMeetingStatus(isCompleted, startDatetime)) {
    case MeetingStatus.COMPLETED:
      return (
        <Badge
          variant="outline"
          className="border-green-200 bg-green-50 text-green-700"
        >
          Completed
        </Badge>
      );
    case MeetingStatus.PAST_INCOMPLETE:
      return (
        <Badge
          variant="outline"
          className="border-gray-300 bg-gray-100 text-gray-700"
        >
          Incomplete
        </Badge>
      );
    case MeetingStatus.SCHEDULED:
      return (
        <Badge
          variant="outline"
          className="border-amber-200 bg-amber-50 text-amber-700"
        >
          Scheduled
        </Badge>
      );
    default:
      return null;
  }
}

/**
 * Renders a meeting's note tags as semicolon-separated plain text. When a
 * past, not-completed meeting has no note tags, shows a plain-text placeholder
 * instead of leaving the cell blank.
 *
 * @param {{note: string[], mentorName: string, menteeName: string, isCompleted: boolean, startDatetime: string}} props
 */
function MeetingNoteCell({
  note,
  mentorName,
  menteeName,
  isCompleted,
  startDatetime,
}) {
  if (note.length === 0) {
    if (
      getMeetingStatus(isCompleted, startDatetime) ===
      MeetingStatus.PAST_INCOMPLETE
    ) {
      return <span className="text-sm italic">No attendance data</span>;
    }
    return null;
  }
  return (
    <span className="text-sm">
      {note
        .map((tag) => noteTagLabel(tag, { mentorName, menteeName }))
        .join("; ")}
    </span>
  );
}

/**
 * Dropdown selector for a meeting's completion state.
 * Disables "Completed" while an absent tag is selected in the meeting's note.
 *
 * @param {{isCompleted: boolean, note: string[], onChange: (isCompleted: boolean) => void}} props
 */
function CompleteStatusSelect({ isCompleted, note, onChange }) {
  return (
    <Select
      value={isCompleted ? "completed" : "incomplete"}
      onValueChange={(v) => onChange(v === "completed")}
    >
      <SelectTrigger aria-label="Complete Status" className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="completed" disabled={hasAbsentTag(note)}>
          Completed
        </SelectItem>
        <SelectItem value="incomplete">Incomplete</SelectItem>
      </SelectContent>
    </Select>
  );
}

/**
 * Popover checkbox list for editing meeting note tags.
 * Reuses the read-only column's name substitution and disables options
 * violating backend mutual-exclusion rules.
 *
 * @param {{
 *   note: string[],
 *   isCompleted: boolean,
 *   mentorName: string,
 *   menteeName: string,
 *   onChange: (tags: string[]) => void
 * }} props
 */
function NoteTagPopover({
  note,
  isCompleted,
  mentorName,
  menteeName,
  onChange,
}) {
  const disabled = getDisabledNoteTags(note, { isCompleted });
  const toggleTag = (tag, checked) =>
    onChange(checked ? [...note, tag] : note.filter((t) => t !== tag));
  const summary = note
    .map((tag) => noteTagLabel(tag, { mentorName, menteeName }))
    .join("; ");

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          aria-label="Note"
          className="flex h-8 w-full items-center justify-between gap-1.5 rounded-lg px-2.5 py-2 text-sm font-normal"
        >
          <span className="truncate">
            {note.length > 0 ? (
              summary
            ) : (
              <span className="text-muted-foreground">Select note tag(s)</span>
            )}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64">
        <div className="flex flex-col gap-2">
          {MEETING_NOTE_TAGS.map((tag) => (
            <label
              key={tag}
              className={`flex items-center gap-2 text-sm ${
                disabled.has(tag) ? "opacity-50" : ""
              }`}
            >
              <Checkbox
                aria-label={noteTagLabel(tag, { mentorName, menteeName })}
                checked={note.includes(tag)}
                disabled={disabled.has(tag)}
                onCheckedChange={(checked) => toggleTag(tag, checked)}
              />
              {noteTagLabel(tag, { mentorName, menteeName })}
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

/**
 * Renders a visual comparison of a field's previous and updated values.
 * The `note` field's tag array is joined into a semicolon-separated
 * string first; other fields' values are already plain strings.
 *
 * @param {{
 *   change: {field: string, label: string, from: (string|string[]), to: (string|string[])},
 *   mentorName: string,
 *   menteeName: string,
 * }} props
 */
function FieldChangeDiff({ change, mentorName, menteeName }) {
  const formatValue = (value) => {
    if (change.field !== "note") return value;
    return value.length > 0
      ? value
          .map((tag) => noteTagLabel(tag, { mentorName, menteeName }))
          .join("; ")
      : "No note";
  };

  return (
    <p className="break-words text-sm text-gray-900 dark:text-gray-100">
      <span className="font-medium">{change.label}:</span>{" "}
      <span className="font-medium text-gray-500 line-through dark:text-gray-400">
        {formatValue(change.from)}
      </span>{" "}
      <span className="text-gray-400 dark:text-gray-500">→</span>{" "}
      <span className="font-medium text-violet-600/85 dark:text-violet-400/85">
        {formatValue(change.to)}
      </span>
    </p>
  );
}

/**
 * A pair's meetings as the console shows them: number, Pacific time range,
 * create time, three-state status and name-substituted attendance tags. With
 * an `editor` in edit mode, each row gets a delete checkbox and its Status and
 * Note cells become editable; a row checked for deletion locks to read-only.
 *
 * @param {{
 *   meetings: Array<{meetingId: string, startDatetime: string, endDatetime: string, isCompleted: boolean, note: string[], createDatetime: string}>,
 *   mentorName: string,
 *   menteeName: string,
 *   editor?: ReturnType<typeof import("@/pages/MentorshipManagement/hooks/useMeetingLogEditor").useMeetingLogEditor>,
 * }} props
 */
const MeetingLogTable = ({ meetings, mentorName, menteeName, editor }) => {
  const isEditing = editor?.isEditing ?? false;
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-sm border-collapse table-fixed">
        <thead>
          <tr className="bg-accent text-left text-xs font-semibold text-accent-foreground uppercase tracking-wide">
            <th className="px-3 py-2 border-b border-border w-20">
              <div className="flex items-center gap-2">
                {isEditing && (
                  <Checkbox
                    aria-label="Select all meetings for deletion"
                    checked={editor.allSelected}
                    onCheckedChange={editor.toggleSelectAll}
                  />
                )}
                #
              </div>
            </th>
            <th className="px-3 py-2 border-b border-l border-border w-52">
              Time Range
            </th>
            <th className="px-3 py-2 border-b border-l border-border w-40">
              Create Datetime
            </th>
            <th className="px-3 py-2 border-b border-l border-border w-36">
              Status
            </th>
            <th className="px-3 py-2 border-b border-l border-border">Note</th>
          </tr>
        </thead>
        <tbody>
          {meetings.map((meeting, index) => {
            const isChecked =
              isEditing && editor.pendingDeleteIds.has(meeting.meetingId);
            const effectiveFields =
              isEditing && !isChecked ? editor.getEffectiveFields(meeting) : null;
            return (
              <tr
                key={meeting.meetingId}
                className={`border-b border-border last:border-b-0 ${isChecked ? "opacity-50" : ""}`}
              >
                <td className="px-3 py-3 align-top">
                  <div className="flex items-center gap-2">
                    {isEditing && (
                      <Checkbox
                        aria-label={`Select meeting ${index + 1} for deletion`}
                        checked={isChecked}
                        onCheckedChange={(checked) =>
                          editor.togglePendingDelete(meeting.meetingId, checked)
                        }
                      />
                    )}
                    {index + 1}
                  </div>
                </td>
                <td className="px-3 py-3 border-l border-border align-top">
                  {formatMeetingTimeRange(
                    meeting.startDatetime,
                    meeting.endDatetime,
                  )}
                </td>
                <td className="px-3 py-3 border-l border-border align-top">
                  {formatCreateDatetime(meeting.createDatetime)}
                </td>
                <td className="px-3 py-3 border-l border-border align-top">
                  {effectiveFields ? (
                    <CompleteStatusSelect
                      isCompleted={effectiveFields.isCompleted}
                      note={effectiveFields.note}
                      onChange={(v) =>
                        editor.patchField(meeting.meetingId, { isCompleted: v })
                      }
                    />
                  ) : (
                    <MeetingStatusCell
                      isCompleted={meeting.isCompleted}
                      startDatetime={meeting.startDatetime}
                    />
                  )}
                </td>
                <td className="px-3 py-3 border-l border-border align-top">
                  {effectiveFields ? (
                    <NoteTagPopover
                      note={effectiveFields.note}
                      isCompleted={effectiveFields.isCompleted}
                      mentorName={mentorName}
                      menteeName={menteeName}
                      onChange={(v) =>
                        editor.patchField(meeting.meetingId, { note: v })
                      }
                    />
                  ) : (
                    <MeetingNoteCell
                      note={meeting.note}
                      mentorName={mentorName}
                      menteeName={menteeName}
                      isCompleted={meeting.isCompleted}
                      startDatetime={meeting.startDatetime}
                    />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

/**
 * Edit, or while editing Cancel / Delete (n) / Update (n). The caller wraps
 * them (a DialogFooter in the dialog, a plain row on the detail page) and
 * decides whether editing is allowed at all.
 *
 * @param {{ editor: Object }} props
 */
export const MeetingLogEditButtons = ({ editor }) =>
  editor.isEditing ? (
    <>
      <Button variant="outline" size="sm" onClick={editor.resetEditState}>
        Cancel
      </Button>
      <Button
        variant="destructive"
        size="sm"
        onClick={() => editor.setConfirmAction("delete")}
        disabled={editor.deleteCount === 0}
      >
        <Trash2 className="h-4 w-4 mr-1" />
        Delete ({editor.deleteCount})
      </Button>
      <Button
        size="sm"
        onClick={() => editor.setConfirmAction("update")}
        disabled={editor.updateCount === 0}
      >
        <Pencil className="h-4 w-4 mr-1" />
        Update ({editor.updateCount})
      </Button>
    </>
  ) : (
    <Button variant="outline" size="sm" onClick={editor.startEditing}>
      Edit
    </Button>
  );

/**
 * The confirmation for the pending update or delete: the affected rows by
 * table position, a before/after line per touched field, and Cancel /
 * Confirm changes. Must sit inside a Dialog.
 *
 * @param {{ editor: Object, mentorName: string, menteeName: string }} props
 */
export const MeetingLogConfirm = ({ editor, mentorName, menteeName }) => {
  const { confirmAction, isSaving } = editor;
  return (
    <>
      <DialogHeader className="sm:text-center">
        <DialogTitle>
          {confirmAction === "delete" ? "Delete meetings?" : "Save changes?"}
        </DialogTitle>
        <DialogDescription className="sr-only">
          Review and confirm this change.
        </DialogDescription>
      </DialogHeader>
      <div className="text-sm text-center">
        <div className="flex flex-col items-center gap-1">
          {confirmAction === "update" && (
            <>
              <p className="flex items-center gap-2">
                <Pencil className="h-4 w-4 shrink-0" />
                Updates: {editor.updateCount}
              </p>
              <div className="w-full max-h-[50vh] overflow-y-auto space-y-2">
                {editor.affectedMeetingRows(editor.updateIds).map((meeting) => (
                  <div
                    key={meeting.meetingId}
                    className="rounded-lg border border-violet-100 bg-violet-50 p-3 text-left dark:border-violet-800/40 dark:bg-violet-950/30"
                  >
                    <p className="break-words text-sm font-medium text-gray-900 dark:text-gray-100">
                      # {meeting.rowNumber}{" "}
                      {formatMeetingTimeRange(
                        meeting.startDatetime,
                        meeting.endDatetime,
                      )}
                    </p>
                    <div className="mt-2 space-y-2">
                      {editor.describeFieldChanges(meeting).map((change) => (
                        <FieldChangeDiff
                          key={change.field}
                          change={change}
                          mentorName={mentorName}
                          menteeName={menteeName}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
          {confirmAction === "delete" && (
            <>
              <p className="flex items-center gap-2">
                <Trash2 className="h-4 w-4 shrink-0" />
                Deletes: {editor.deleteCount}
              </p>
              <div className="max-h-[50vh] overflow-y-auto">
                {editor
                  .affectedMeetingRows([...editor.pendingDeleteIds])
                  .map((meeting) => (
                    <p
                      key={meeting.meetingId}
                      className="break-words text-sm font-medium text-gray-900 dark:text-gray-100"
                    >
                      # {meeting.rowNumber}{" "}
                      {formatMeetingTimeRange(
                        meeting.startDatetime,
                        meeting.endDatetime,
                      )}
                    </p>
                  ))}
              </div>
            </>
          )}
        </div>
        <p className="mt-2">These changes cannot be undone.</p>
      </div>
      <div className="flex justify-center gap-2">
        <Button
          variant="outline"
          onClick={() => editor.setConfirmAction(null)}
          disabled={isSaving}
        >
          Cancel
        </Button>
        <Button onClick={editor.handleConfirm} disabled={isSaving}>
          Confirm changes
        </Button>
      </div>
    </>
  );
};

export default MeetingLogTable;
