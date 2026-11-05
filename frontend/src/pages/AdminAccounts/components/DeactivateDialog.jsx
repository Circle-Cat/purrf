import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { accountLabel } from "@/utils/userName";

/**
 * Confirm deactivating an account.
 *
 * Deactivation is for someone who no longer wants to use Purrf, so the copy
 * carries no implication of fault and the note stays optional -- unlike a
 * block, where a reason is required.
 *
 * @param {{open: boolean, onOpenChange: Function,
 *          account?: {userId?: number, firstName?: string, lastName?: string,
 *                     name?: string, primaryEmail?: string}|null,
 *          onConfirm: Function, submitting?: boolean}} props
 * @param {boolean} props.open Whether the dialog is showing.
 * @param {Function} props.onOpenChange Called with the next open state.
 * @param {object|null} [props.account] The account being deactivated; named in
 *   the title when it resolves to something. Either a first/last pair or a
 *   single resolved `name`.
 * @param {Function} props.onConfirm Called with the trimmed note, or null when
 *   the note was left blank.
 * @param {boolean} [props.submitting] Disables both buttons while in flight.
 * @returns {JSX.Element}
 */
const DeactivateDialog = ({
  open,
  onOpenChange,
  account,
  onConfirm,
  submitting = false,
}) => {
  const [note, setNote] = useState("");

  useEffect(() => {
    if (open) setNote("");
  }, [open]);

  const name = accountLabel(account);

  const handleConfirm = () => {
    if (submitting) return;
    onConfirm?.(note.trim() || null);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {name ? `Deactivate account — ${name}` : "Deactivate account"}
          </DialogTitle>
          <DialogDescription className="text-slate-700">
            For someone who no longer wants to use Purrf.
          </DialogDescription>
        </DialogHeader>
        <ul className="space-y-1 text-sm text-slate-700">
          <li>· Every page becomes inaccessible — they can still sign in</li>
          <li>· Nothing is deleted; reactivating restores everything</li>
          <li>· Sign-in methods and emails are left untouched</li>
        </ul>
        <div className="space-y-1">
          <Label htmlFor="deactivate-note">
            Note — optional, kept with the record
          </Label>
          <Textarea
            id="deactivate-note"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange?.(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={submitting}>
            Deactivate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default DeactivateDialog;
