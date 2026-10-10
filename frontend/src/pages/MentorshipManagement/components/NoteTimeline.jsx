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
import { userDisplayName } from "@/utils/userName";
import { unresolvedPersonLabel } from "@/pages/Recruiting/components/personLabel";
import { MEETING_TIMEZONE } from "@/pages/MentorshipManagement/utils/attendanceIssues";
import { stageLabel } from "@/pages/MentorshipManagement/components/email/emailLabels";

// The backend refuses anything longer.
const MAX_NOTE_LENGTH = 5000;

const TAG_LABELS = {
  status_change: "Status change",
  matching_exemption: "Exemption",
  no_show: "No show",
  red_flag: "Red flag",
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

const at = (iso) => formatInTz(iso, MEETING_TIMEZONE, "yyyy-MM-dd HH:mm");

const NoteEntry = ({ note, partner }) => (
  <li className="text-sm">
    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
      {TAG_LABELS[note.tag] && (
        <Badge variant="secondary">{TAG_LABELS[note.tag]}</Badge>
      )}
      {partner && <span>with {partner}</span>}
      <span>
        {note.author?.name ?? unresolvedPersonLabel(note.author?.userId)} ·{" "}
        {at(note.createdAt)}
      </span>
      {note.requestId != null && <span>(via approval)</span>}
    </div>
    <p className="mt-1 whitespace-pre-wrap break-words">{note.body}</p>
  </li>
);

const SendEntry = ({ send }) => (
  <li className="text-sm">
    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
      <Badge variant="secondary">Notification</Badge>
      <span>Kit · {at(send.at)}</span>
    </div>
    <p className="mt-1 break-words">
      {stageLabel(send.stage)} · {send.subject}
    </p>
    {send.delivered ? (
      <p className="text-xs text-slate-500">Sent</p>
    ) : (
      <p className="text-xs text-red-600">Not sent. {send.reason}</p>
    )}
  </li>
);

/**
 * Everything about a person in one round, newest first: the notes written
 * about them, whatever kind, and the Kit notifications that went out to them
 * or failed to. A note an approval wrote says so.
 *
 * @param {{notes: Object[], sends?: Object[], roundId: number|string,
 *          userId: number|string, canAdd: boolean, onAdded: () => void,
 *          pairs?: Object[]}} props
 *   pairs: the round's pairs, to name the partner of the pair a note is
 *   about.
 */
const NoteTimeline = ({
  notes,
  sends = [],
  roundId,
  userId,
  canAdd,
  onAdded,
  pairs = [],
}) => {
  const [adding, setAdding] = useState(false);
  const partnerOf = new Map(
    pairs.map((pair) => [pair.pairId, userDisplayName(pair.partner)]),
  );
  const entries = [
    ...notes.map((note) => ({
      key: `note-${note.noteId}`,
      time: note.createdAt,
      note,
    })),
    ...sends.map((send) => ({
      key: `send-${send.sendId}`,
      time: send.at,
      send,
    })),
  ].sort((a, b) => new Date(b.time) - new Date(a.time));

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
      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">No notes yet.</p>
      ) : (
        <ul className="space-y-3">
          {entries.map(({ key, note, send }) =>
            note ? (
              <NoteEntry
                key={key}
                note={note}
                partner={
                  note.pairId != null ? partnerOf.get(note.pairId) : undefined
                }
              />
            ) : (
              <SendEntry key={key} send={send} />
            ),
          )}
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
