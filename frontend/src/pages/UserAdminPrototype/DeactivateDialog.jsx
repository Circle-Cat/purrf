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
import { fullName } from "@/pages/UserAdminPrototype/accountState";

/**
 * DeactivateDialog
 *
 * Deactivation is for someone who no longer wants the account — they asked,
 * or they left and are not keeping it. It is not a sanction, so the copy
 * carries no wrongdoing and the note is optional.
 *
 * @param {{user: object|null, onCancel: Function, onConfirm: Function}} props
 * @returns {JSX.Element}
 */
const DeactivateDialog = ({ user, onCancel, onConfirm }) => {
  const [note, setNote] = useState("");
  if (!user) return null;

  const close = () => {
    setNote("");
    onCancel();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Deactivate account — {fullName(user)}</DialogTitle>
        </DialogHeader>

        <p className="text-sm text-slate-600">
          For someone who no longer wants to use Purrf.
        </p>
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
          <li>Every page becomes inaccessible — they can still sign in</li>
          <li>Nothing is deleted; reactivating restores everything</li>
          <li>Sign-in methods and emails are left untouched</li>
        </ul>

        <div className="space-y-1.5">
          <label
            className="text-sm font-medium text-slate-900"
            htmlFor="deactivate-note"
          >
            Note — optional, kept with the record
          </label>
          <Textarea
            id="deactivate-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="requested by email 2026-09-01"
            rows={2}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              onConfirm(note.trim());
              setNote("");
            }}
          >
            Deactivate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default DeactivateDialog;
