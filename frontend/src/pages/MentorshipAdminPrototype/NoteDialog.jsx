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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  NOTE_LABELS,
  RECORDED_TAGS,
} from "@/pages/MentorshipAdminPrototype/mockData";

/**
 * NoteDialog
 *
 * Writes a note. The tag dropdown holds only the *recorded* kinds — things
 * that happened, like a reminder having gone out.
 *
 * "No show", "red flag" and "partner change" are deliberately absent: those
 * are judgements with consequences, and they are raised as a request instead.
 * Putting them in this dropdown would make an approval look optional.
 *
 * Clicking a mark on the Pairs table opens this same box with the kind fixed
 * (`target.fixedTag`), so a reply summary can go in with the mark — or not.
 *
 * @returns {JSX.Element|null}
 */
const NoteDialog = ({ target, onClose, onSave }) => {
  const [tag, setTag] = useState("none");
  const [body, setBody] = useState("");
  if (!target) return null;

  const close = () => {
    setTag("none");
    setBody("");
    onClose();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{target.title ?? "Add a note"}</DialogTitle>
        </DialogHeader>

        {target.fixedTag ? null : (
          <>
            <label className="text-xs text-slate-500">Kind</label>
            <Select value={tag} onValueChange={setTag}>
              <SelectTrigger className="text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Plain note</SelectItem>
                {RECORDED_TAGS.map((t) => (
                  <SelectItem key={t} value={t}>
                    {NOTE_LABELS[t]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        )}

        <label className="mt-2 text-xs text-slate-500">
          What happened (may be left empty)
        </label>
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={4}
          placeholder="Sent on Teams. No reply yet."
        />
        <p className="text-xs text-slate-500">
          Leaving this empty is fine — a reply often arrives days later, and a
          box that forces you to invent something now just gets filled with
          noise. Come back and add a second note when you hear.
        </p>

        <DialogFooter>
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              onSave({
                tag: target.fixedTag ?? (tag === "none" ? null : tag),
                body,
              });
              setTag("none");
              setBody("");
            }}
          >
            {target.mark ? "Mark" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default NoteDialog;
