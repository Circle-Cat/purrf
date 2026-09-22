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
import { APPROVAL_ACTIONS } from "@/pages/MentorshipAdminPrototype/mockData";

/**
 * RaiseRequestDialog
 *
 * The entry for anything with consequences. Nothing here takes effect when you
 * press the button — it becomes a pending request, and somebody holding the
 * approve permission decides it.
 *
 * Toggle "Approve" off in the header to see what the raiser sees afterwards:
 * the request is in the queue and the person's status has not moved.
 *
 * @returns {JSX.Element|null}
 */
const RaiseRequestDialog = ({ target, onClose, onSave }) => {
  const [action, setAction] = useState(APPROVAL_ACTIONS[0].key);
  const [reason, setReason] = useState("");
  if (!target) return null;

  const close = () => {
    setAction(APPROVAL_ACTIONS[0].key);
    setReason("");
    onClose();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Raise a change — {target.targetLabel}</DialogTitle>
        </DialogHeader>

        <label className="text-xs text-slate-500">
          What are you asking for
        </label>
        <Select value={action} onValueChange={setAction}>
          <SelectTrigger className="text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {APPROVAL_ACTIONS.map((a) => (
              <SelectItem key={a.key} value={a.key}>
                {a.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <label className="mt-2 text-xs text-slate-500">Why</label>
        <Textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={4}
          placeholder="Five days past the first-contact deadline. No reply on email or Teams."
        />
        <p className="text-xs text-slate-500">
          Nothing changes yet. This goes to whoever holds the approve
          permission, and the status only moves once they decide.
        </p>

        <DialogFooter>
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button
            disabled={!reason.trim()}
            onClick={() => {
              onSave({ action, reason });
              setAction(APPROVAL_ACTIONS[0].key);
              setReason("");
            }}
          >
            Send for approval
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default RaiseRequestDialog;
