import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { NOTE_LABELS } from "@/pages/MentorshipAdminPrototype/mockData";

/**
 * NoteDialog
 *
 * Writes a note, in one of three shapes:
 *
 *   - a plain note, from "Add a note";
 *   - marking a notification sent some other way (`target.notifySteps`) —
 *     one person at a time, from their page, and the note of how it went out
 *     is required, since that note is the only record there is;
 *   - a mark with its kind fixed (`target.fixedTag`), such as first contact,
 *     where a reply summary may go in with it or not.
 *
 * "No show", "red flag" and "partner change" are never offered: those are
 * judgements with consequences, and they are raised as a request instead.
 *
 * @returns {JSX.Element|null}
 */
const NoteDialog = ({ target, onClose, onSave }) => {
  const [tag, setTag] = useState("");
  const [body, setBody] = useState("");
  if (!target) return null;

  const notifying = Boolean(target.notifySteps);
  const ready = !notifying || (tag && body.trim());
  const close = () => {
    setTag("");
    setBody("");
    onClose();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{target.title ?? "Add a note"}</DialogTitle>
        </DialogHeader>

        {notifying ? (
          <>
            <label className="text-xs text-slate-500" htmlFor="notify-step">
              Which notification
            </label>
            <select
              id="notify-step"
              className="w-full rounded-md border border-slate-300 p-2 text-sm"
              value={tag}
              onChange={(e) => setTag(e.target.value)}
            >
              <option value="">Select a notification…</option>
              {target.notifySteps.map((s) => (
                <option key={s.tag} value={s.tag}>
                  {NOTE_LABELS[s.tag]}
                </option>
              ))}
            </select>
          </>
        ) : null}

        <label className="mt-2 text-xs text-slate-500">
          {notifying
            ? "How it was sent (required)"
            : "What happened (may be left empty)"}
        </label>
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={4}
          placeholder="Sent on Teams. No reply yet."
        />
        <p className="text-xs text-slate-500">
          {notifying
            ? "Purrf did not send this one, so this note is the only record that it went out — say where and when."
            : "Leaving this empty is fine — a reply often arrives days later, and a box that forces you to invent something now just gets filled with noise. Come back and add a second note when you hear."}
        </p>

        <DialogFooter>
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button
            disabled={!ready}
            onClick={() => {
              onSave({
                tag: target.fixedTag ?? (notifying ? tag : null),
                body,
              });
              setTag("");
              setBody("");
            }}
          >
            {target.mark ? "Mark" : notifying ? "Mark as notified" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default NoteDialog;
