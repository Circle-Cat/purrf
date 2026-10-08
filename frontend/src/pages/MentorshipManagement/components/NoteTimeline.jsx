import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { addParticipantNote } from "@/api/mentorshipApi";
import { formatInTz } from "@/utils/dateTime";
import { MEETING_TIMEZONE } from "@/pages/MentorshipManagement/utils/attendanceIssues";

// The backend refuses anything longer.
const MAX_NOTE_LENGTH = 5000;

const TAG_LABELS = {
  status_change: "Status change",
  matching_exemption: "Exemption",
};

/**
 * Write a plain-text note on a person in a round. No tag to pick: tagged
 * notes are written by the actions that produce them.
 *
 * @param {{open: boolean, onOpenChange: (open: boolean) => void,
 *          roundId: number|string, userId: number|string,
 *          onAdded: () => void}} props
 */
export const AddNoteDialog = ({
  open,
  onOpenChange,
  roundId,
  userId,
  onAdded,
}) => {
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const trimmed = body.trim();

  const save = async () => {
    setSaving(true);
    try {
      await addParticipantNote(roundId, userId, trimmed);
      setBody("");
      onOpenChange(false);
      onAdded();
    } catch (err) {
      toast.error(
        err?.response?.data?.message ??
          "Couldn't save the note. Please try again.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add a note</DialogTitle>
          <DialogDescription>
            Notes cannot be edited or deleted once saved.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="participant-note">Note</Label>
          <Textarea
            id="participant-note"
            value={body}
            maxLength={MAX_NOTE_LENGTH}
            onChange={(e) => setBody(e.target.value)}
            rows={5}
          />
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button onClick={save} disabled={saving || trimmed === ""}>
            Save note
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

/**
 * Everything written about a person in one round, in the order the API
 * sends it (newest first), whatever kind it is. A note an approval wrote
 * says so.
 *
 * @param {{notes: Object[], roundId: number|string, userId: number|string,
 *          canAdd: boolean, onAdded: () => void}} props
 */
const NoteTimeline = ({ notes, roundId, userId, canAdd, onAdded }) => {
  const [adding, setAdding] = useState(false);
  return (
    <section>
      <header className="mb-2 flex items-center gap-3">
        <h3 className="text-sm font-semibold">Timeline</h3>
        {canAdd && (
          <Button
            size="sm"
            variant="outline"
            className="ml-auto"
            onClick={() => setAdding(true)}
          >
            Add a note
          </Button>
        )}
      </header>
      {notes.length === 0 ? (
        <p className="text-sm text-muted-foreground">No notes yet.</p>
      ) : (
        <ul className="space-y-3">
          {notes.map((note) => (
            <li key={note.noteId} className="text-sm">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                {TAG_LABELS[note.tag] && (
                  <Badge variant="secondary">{TAG_LABELS[note.tag]}</Badge>
                )}
                <span>
                  {note.author?.name
                    ? `${note.author.name} (ID ${note.author.userId})`
                    : `ID ${note.author?.userId}`}{" "}
                  ·{" "}
                  {formatInTz(
                    note.createdAt,
                    MEETING_TIMEZONE,
                    "yyyy-MM-dd HH:mm",
                  )}
                </span>
                {note.requestId != null && <span>(via approval)</span>}
              </div>
              <p className="mt-1 whitespace-pre-wrap break-words">
                {note.body}
              </p>
            </li>
          ))}
        </ul>
      )}
      {canAdd && (
        <AddNoteDialog
          open={adding}
          onOpenChange={setAdding}
          roundId={roundId}
          userId={userId}
          onAdded={onAdded}
        />
      )}
    </section>
  );
};

export default NoteTimeline;
