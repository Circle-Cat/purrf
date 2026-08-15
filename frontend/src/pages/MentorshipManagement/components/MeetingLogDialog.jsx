import { useState, useEffect } from "react";
import { ChevronDown, Loader2, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
import { getMeetingStatus } from "@/utils/meetingStatusCalculator";
import { MeetingStatus } from "@/constants/MeetingStatus";
import { MEETING_NOTE_TAGS } from "@/constants/MeetingNoteTags";
import {
  getDisabledNoteTags,
  hasAbsentTag,
  noteTagLabel,
} from "@/pages/MentorshipManagement/utils/meetingNoteTags";

const ROLE_LABELS = { mentor: "Mentor", mentee: "Mentee" };
const MEETING_TIMEZONE = "America/Los_Angeles";

/**
 * Formats a UTC meeting start/end datetime as a Pacific Time date + time range
 * string, e.g. "2026-04-06 · 15:30 – 16:30".
 *
 * @param {string} startDatetime - UTC ISO-8601 start datetime.
 * @param {string} endDatetime - UTC ISO-8601 end datetime.
 * @returns {string} Formatted Pacific Time date + time range.
 */
function formatMeetingTimeRange(startDatetime, endDatetime) {
  const date = formatInTz(startDatetime, MEETING_TIMEZONE, "yyyy-MM-dd");
  const start = formatInTz(startDatetime, MEETING_TIMEZONE, "HH:mm");
  const end = formatInTz(endDatetime, MEETING_TIMEZONE, "HH:mm");
  return `${date} · ${start} – ${end}`;
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
 * Dialog showing a pair's full meeting log for a round. Read-only by default;
 * a non-empty v2 pair gets an Edit mode for Complete Status/Note and batch
 * deletion. Update and delete are independent actions, each sent as its own
 * request and each gated behind its own confirmation. On success, the dialog
 * itself never closes, but edit mode exits back to the read-only view with
 * the latest `meetings` data, the same as on first opening it.
 *
 * The header renders immediately from the row data already available to
 * the caller; it never waits for the fetch. Only the body switches between
 * loading, error, empty, and table states based on `loading`, `error`, and
 * `meetings`.
 *
 * @param {{
 *   open: boolean,
 *   onOpenChange: (open: boolean) => void,
 *   roundName: string,
 *   roundVersion: "v1" | "v2" | null,
 *   subjectName: string,
 *   subjectRole: "mentor" | "mentee",
 *   partnerName: string,
 *   partnerRole: "mentor" | "mentee",
 *   meetings: Array<{meetingId: string, startDatetime: string, endDatetime: string, isCompleted: boolean, note: string[], createDatetime: string}>,
 *   loading: boolean,
 *   error: boolean,
 *   onSave: (batch: {updates: Object[], deletes: string[]}) => Promise<void>,
 * }} props
 */
const MeetingLogDialog = ({
  open,
  onOpenChange,
  roundName,
  roundVersion,
  subjectName,
  subjectRole,
  partnerName,
  partnerRole,
  meetings,
  loading,
  error,
  onSave,
}) => {
  const mentorName = subjectRole === "mentor" ? subjectName : partnerName;
  const menteeName = subjectRole === "mentee" ? subjectName : partnerName;
  const [isEditing, setIsEditing] = useState(false);
  const [pendingUpdates, setPendingUpdates] = useState({});
  const [pendingDeleteIds, setPendingDeleteIds] = useState(new Set());
  const [confirmAction, setConfirmAction] = useState(null); // null | "update" | "delete"
  const [isSaving, setIsSaving] = useState(false);
  const canEdit = roundVersion === "v2" && meetings.length > 0;

  const updateIds = Object.keys(pendingUpdates).filter(
    (id) => !pendingDeleteIds.has(id),
  );
  const updateCount = updateIds.length;
  const deleteCount = pendingDeleteIds.size;

  // Row number matches the table's own "#" column.
  const affectedMeetingRows = (ids) =>
    meetings
      .map((meeting, i) => ({ ...meeting, rowNumber: i + 1 }))
      .filter((meeting) => ids.includes(meeting.meetingId));

  /**
   * Generates a list of changed fields between the original meeting and its pending patch.
   *
   * @param {{meetingId: string, isCompleted: boolean, note: string[]}} meeting - The original meeting data.
   * @returns {Array<{field: string, label: string, from: (string|string[]), to: (string|string[])}>} A list of changes per field.
   */
  const describeFieldChanges = (meeting) => {
    const patch = pendingUpdates[meeting.meetingId] ?? {};
    const changes = [];
    if (patch.isCompleted !== undefined) {
      const statusLabel = (v) => (v ? "Completed" : "Incomplete");
      changes.push({
        field: "isCompleted",
        label: "Complete Status",
        from: statusLabel(meeting.isCompleted),
        to: statusLabel(patch.isCompleted),
      });
    }
    if (patch.note !== undefined) {
      changes.push({
        field: "note",
        label: "Note",
        from: meeting.note,
        to: patch.note,
      });
    }
    return changes;
  };

  const resetEditState = () => {
    setIsEditing(false);
    setPendingUpdates({});
    setPendingDeleteIds(new Set());
  };

  useEffect(() => {
    if (open) return;
    setConfirmAction(null);
    resetEditState();
  }, [open]);

  const getEffectiveFields = (meeting) => ({
    isCompleted:
      pendingUpdates[meeting.meetingId]?.isCompleted ?? meeting.isCompleted,
    note: pendingUpdates[meeting.meetingId]?.note ?? meeting.note,
  });

  const patchField = (meetingId, patch) =>
    setPendingUpdates((prev) => {
      const merged = { ...prev[meetingId], ...patch };
      const original = meetings.find((m) => m.meetingId === meetingId);
      const isCompleted = merged.isCompleted ?? original.isCompleted;
      const note = merged.note ?? original.note;
      const matchesOriginal =
        isCompleted === original.isCompleted &&
        note.length === original.note.length &&
        note.every((tag) => original.note.includes(tag));
      if (matchesOriginal) {
        const { [meetingId]: _removed, ...rest } = prev;
        return rest;
      }
      return { ...prev, [meetingId]: merged };
    });

  const togglePendingDelete = (meetingId, checked) =>
    setPendingDeleteIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(meetingId);
      else next.delete(meetingId);
      return next;
    });

  const allSelected =
    meetings.length > 0 &&
    meetings.every((m) => pendingDeleteIds.has(m.meetingId));

  const toggleSelectAll = (checked) =>
    setPendingDeleteIds(
      checked ? new Set(meetings.map((m) => m.meetingId)) : new Set(),
    );

  const buildUpdatePayload = () => ({
    updates: Object.entries(pendingUpdates)
      .filter(([meetingId]) => !pendingDeleteIds.has(meetingId))
      .map(([meetingId, fields]) => ({
        meetingId,
        ...fields,
      })),
    deletes: [],
  });

  const buildDeletePayload = () => ({
    updates: [],
    deletes: [...pendingDeleteIds],
  });

  const handleConfirm = async () => {
    const action = confirmAction;
    setIsSaving(true);
    try {
      await onSave(
        action === "delete" ? buildDeletePayload() : buildUpdatePayload(),
      );
      setConfirmAction(null);
      resetEditState();
    } catch (err) {
      const msg = err?.response?.data?.message || err?.message;
      toast.error(
        msg ?? "Couldn't save meeting log changes. Please try again.",
      );
      setConfirmAction(null);
    } finally {
      setIsSaving(false);
    }
  };

  const handleOpenChange = (next) => {
    if (!next && confirmAction) {
      setConfirmAction(null);
      return;
    }
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className={`z-[200] max-h-[85vh] overflow-y-auto ${confirmAction ? "sm:max-w-lg" : "sm:max-w-5xl"}`}
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        {confirmAction ? (
          <>
            <DialogHeader className="sm:text-center">
              <DialogTitle>
                {confirmAction === "delete"
                  ? "Delete meetings?"
                  : "Save changes?"}
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
                      Updates: {updateCount}
                    </p>
                    <div className="w-full max-h-[50vh] overflow-y-auto space-y-2">
                      {affectedMeetingRows(updateIds).map((meeting) => (
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
                            {describeFieldChanges(meeting).map((change) => (
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
                      Deletes: {deleteCount}
                    </p>
                    <div className="max-h-[50vh] overflow-y-auto">
                      {affectedMeetingRows([...pendingDeleteIds]).map(
                        (meeting) => (
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
                        ),
                      )}
                    </div>
                  </>
                )}
              </div>
              <p className="mt-2">These changes cannot be undone.</p>
            </div>
            <div className="flex justify-center gap-2">
              <Button
                variant="outline"
                onClick={() => setConfirmAction(null)}
                disabled={isSaving}
              >
                Cancel
              </Button>
              <Button onClick={handleConfirm} disabled={isSaving}>
                Confirm changes
              </Button>
            </div>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>
                Meeting Log — {subjectName} ({ROLE_LABELS[subjectRole]}) with{" "}
                {partnerName} ({ROLE_LABELS[partnerRole]}) · {roundName}
              </DialogTitle>
              <DialogDescription className="sr-only">
                Each meeting's datetime, status, and notes for this pair.
              </DialogDescription>
            </DialogHeader>

            {loading ? (
              <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                Loading meeting log…
              </div>
            ) : error ? (
              <p className="py-8 text-center text-sm font-medium text-destructive">
                Couldn't load meeting log. Close and reopen to try again.
              </p>
            ) : meetings.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No meetings recorded yet.
              </p>
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full text-sm border-collapse table-fixed">
                  <thead>
                    <tr className="bg-accent text-left text-xs font-semibold text-accent-foreground uppercase tracking-wide">
                      <th className="px-3 py-2 border-b border-border w-20">
                        <div className="flex items-center gap-2">
                          {isEditing && (
                            <Checkbox
                              aria-label="Select all meetings for deletion"
                              checked={allSelected}
                              onCheckedChange={toggleSelectAll}
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
                      <th className="px-3 py-2 border-b border-l border-border">
                        Note
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {meetings.map((meeting, index) => {
                      const isChecked = pendingDeleteIds.has(meeting.meetingId);
                      const effectiveFields =
                        isEditing && !isChecked
                          ? getEffectiveFields(meeting)
                          : null;
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
                                    togglePendingDelete(
                                      meeting.meetingId,
                                      checked,
                                    )
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
                                  patchField(meeting.meetingId, {
                                    isCompleted: v,
                                  })
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
                                  patchField(meeting.meetingId, { note: v })
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
            )}

            {canEdit && (
              <DialogFooter>
                {!isEditing && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setIsEditing(true)}
                  >
                    Edit
                  </Button>
                )}
                {isEditing && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={resetEditState}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setConfirmAction("delete")}
                      disabled={deleteCount === 0}
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      Delete ({deleteCount})
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => setConfirmAction("update")}
                      disabled={updateCount === 0}
                    >
                      <Pencil className="h-4 w-4 mr-1" />
                      Update ({updateCount})
                    </Button>
                  </>
                )}
              </DialogFooter>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default MeetingLogDialog;
