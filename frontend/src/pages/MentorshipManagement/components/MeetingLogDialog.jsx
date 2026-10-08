import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MEETING_TIMEZONE } from "@/pages/MentorshipManagement/utils/attendanceIssues";
import MeetingLogTable, {
  MeetingLogConfirm,
  MeetingLogEditButtons,
} from "@/pages/MentorshipManagement/components/MeetingLogTable";
import { useMeetingLogEditor } from "@/pages/MentorshipManagement/hooks/useMeetingLogEditor";

const ROLE_LABELS = { mentor: "Mentor", mentee: "Mentee" };

/**
 * Dialog showing a pair's full meeting log for a round. Read-only by default;
 * a non-empty v2 pair gets an Edit mode for Complete Status/Note and batch
 * deletion. Update and delete are independent actions, each sent as its own
 * request and each gated behind its own confirmation, which takes the
 * dialog's place until it is confirmed or cancelled. On success, the dialog
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
  const editor = useMeetingLogEditor({ meetings, onSave });
  const canEdit = roundVersion === "v2" && meetings.length > 0;
  const { confirmAction, setConfirmAction, resetEditState } = editor;

  useEffect(() => {
    if (open) return;
    setConfirmAction(null);
    resetEditState();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

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
          <MeetingLogConfirm
            editor={editor}
            mentorName={mentorName}
            menteeName={menteeName}
          />
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>
                Meeting Log — {subjectName} ({ROLE_LABELS[subjectRole]}) with{" "}
                {partnerName} ({ROLE_LABELS[partnerRole]}) · {roundName}
              </DialogTitle>
              <DialogDescription>
                Meeting details for this pair. All times are in{" "}
                {MEETING_TIMEZONE}.
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
              <MeetingLogTable
                meetings={meetings}
                mentorName={mentorName}
                menteeName={menteeName}
                editor={editor}
              />
            )}

            {canEdit && (
              <DialogFooter>
                <MeetingLogEditButtons editor={editor} />
              </DialogFooter>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default MeetingLogDialog;
