import { useState } from "react";
import { toast } from "sonner";

/**
 * The batch Edit mode of a pair's meeting log: which rows are edited or
 * marked for deletion, which confirmation is showing, and sending the batch.
 * Update and delete are independent actions, each sent as its own request.
 * On success edit mode exits back to the read-only view; on failure the
 * server's message is toasted and the pending edits are kept for a retry.
 *
 * @param {{
 *   meetings: Array<{meetingId: string, isCompleted: boolean, note: string[]}>,
 *   onSave: (batch: {updates: Object[], deletes: string[]}) => Promise<void>,
 * }} args
 */
export const useMeetingLogEditor = ({ meetings, onSave }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [pendingUpdates, setPendingUpdates] = useState({});
  const [pendingDeleteIds, setPendingDeleteIds] = useState(new Set());
  const [confirmAction, setConfirmAction] = useState(null); // null | "update" | "delete"
  const [isSaving, setIsSaving] = useState(false);

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

  return {
    isEditing,
    startEditing: () => setIsEditing(true),
    resetEditState,
    pendingDeleteIds,
    updateIds,
    updateCount,
    deleteCount,
    confirmAction,
    setConfirmAction,
    isSaving,
    affectedMeetingRows,
    describeFieldChanges,
    getEffectiveFields,
    patchField,
    togglePendingDelete,
    allSelected,
    toggleSelectAll,
    handleConfirm,
  };
};
