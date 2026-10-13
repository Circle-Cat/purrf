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
import { userDisplayName } from "@/utils/userName";
import { unresolvedPersonLabel } from "@/pages/Recruiting/components/personLabel";
import { formatPacific } from "@/pages/MentorshipManagement/utils/attendanceIssues";
import EmailThreadCard from "@/components/email/EmailThreadCard";
import { threadActivityAt } from "@/components/email/emailThreads";
import { stageLabel } from "@/pages/MentorshipManagement/components/email/emailLabels";
import MarkNotifiedDialog from "@/pages/MentorshipManagement/components/email/MarkNotifiedDialog";

// The backend refuses anything longer.
const MAX_NOTE_LENGTH = 5000;

const TAG_LABELS = {
  status_change: "Status change",
  matching_exemption: "Exemption",
  no_show: "No show",
  red_flag: "Red flag",
};

const tagLabel = (note) =>
  note.tag === "notified"
    ? `Marked as notified: ${stageLabel(note.notificationStage)}`
    : TAG_LABELS[note.tag];

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

const at = formatPacific;

const NoteEntry = ({ note, partner }) => (
  <li className="text-sm">
    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
      {tagLabel(note) && <Badge variant="secondary">{tagLabel(note)}</Badge>}
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

const EmailEntry = ({ thread, canReply, onReply, attachmentUrl }) => {
  const activity = threadActivityAt(thread);
  return (
    <li className="text-sm">
      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <Badge variant="secondary">Email</Badge>
        {activity && <span>{at(activity)}</span>}
      </div>
      <EmailThreadCard
        thread={thread}
        formatTime={at}
        attachmentUrl={attachmentUrl}
        canReply={canReply}
        onReply={onReply}
      />
    </li>
  );
};

const refreshedText = (count) =>
  count === 0
    ? "No new messages"
    : `${count} new ${count === 1 ? "message" : "messages"}`;

/**
 * Everything about a person in one round, newest first: the notes written
 * about them, whatever kind, the Kit notifications that went out to them or
 * failed to, and the email threads with them, each placed by its newest
 * message. A note an approval wrote says so.
 *
 * @param {{notes: Object[], sends?: Object[], roundId: number|string,
 *          userId: number|string, canAdd: boolean, onAdded: () => void,
 *          pairs?: Object[], canMarkNotified?: boolean, personName?: string,
 *          markStageOptions?: Object[], notifiedStages?: string[],
 *          emailThreads?: Object[], canReply?: boolean,
 *          onReply?: (thread: Object) => void,
 *          attachmentUrl?: (messageId: number, index: number) => string,
 *          onRefreshEmails?: () => Promise<number|null>,
 *          emailLoadError?: boolean}} props
 *   pairs: the round's pairs, to name the partner of the pair a note is
 *   about. canMarkNotified: offer Mark as notified beside Add a note, for
 *   the person personName, among markStageOptions, with notifiedStages
 *   already reached. onRefreshEmails: pulls new messages and resolves to how
 *   many came in, or null when it failed; without it there is no Refresh
 *   emails.
 */
const NoteTimeline = ({
  notes,
  sends = [],
  roundId,
  userId,
  canAdd,
  onAdded,
  pairs = [],
  canMarkNotified = false,
  personName,
  markStageOptions = [],
  notifiedStages = [],
  emailThreads = [],
  canReply = false,
  onReply,
  attachmentUrl,
  onRefreshEmails,
  emailLoadError = false,
}) => {
  const [adding, setAdding] = useState(false);
  const [marking, setMarking] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshed, setRefreshed] = useState("");
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
    ...emailThreads.map((thread) => ({
      key: `email-${thread.threadId}`,
      time: threadActivityAt(thread),
      thread,
    })),
  ].sort((a, b) => new Date(b.time) - new Date(a.time));

  const refreshEmails = async () => {
    setRefreshed("");
    setRefreshing(true);
    try {
      const count = await onRefreshEmails();
      if (count != null) setRefreshed(refreshedText(count));
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <section>
      <header className="mb-2 flex items-center gap-3">
        <h3 className="text-sm font-semibold">Timeline</h3>
        <div className="ml-auto flex gap-2">
          {onRefreshEmails && (
            <Button
              size="sm"
              variant="ghost"
              disabled={refreshing}
              onClick={refreshEmails}
            >
              Refresh emails
            </Button>
          )}
          {canAdd && canMarkNotified && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setMarking(true)}
            >
              Mark as notified
            </Button>
          )}
          {canAdd && (
            <Button size="sm" variant="outline" onClick={() => setAdding(true)}>
              Add a note
            </Button>
          )}
        </div>
      </header>
      {onRefreshEmails && (
        // Mounted before any result so screen readers announce the first one.
        <p
          role="status"
          className={refreshed ? "mb-2 text-xs text-slate-500" : undefined}
        >
          {refreshed}
        </p>
      )}
      {emailLoadError && (
        <p className="mb-2 text-xs text-red-700">Couldn't load emails.</p>
      )}
      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing here yet.</p>
      ) : (
        <ul className="space-y-3">
          {entries.map(({ key, note, send, thread }) => {
            if (note) {
              return (
                <NoteEntry
                  key={key}
                  note={note}
                  partner={
                    note.pairId != null ? partnerOf.get(note.pairId) : undefined
                  }
                />
              );
            }
            if (send) return <SendEntry key={key} send={send} />;
            return (
              <EmailEntry
                key={key}
                thread={thread}
                canReply={canReply}
                onReply={onReply}
                attachmentUrl={attachmentUrl}
              />
            );
          })}
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
      {canAdd && canMarkNotified && marking && (
        <MarkNotifiedDialog
          open
          onOpenChange={setMarking}
          roundId={roundId}
          people={[{ userId, name: personName, notifiedStages }]}
          stageOptions={markStageOptions}
          onMarked={onAdded}
        />
      )}
    </section>
  );
};

export default NoteTimeline;
