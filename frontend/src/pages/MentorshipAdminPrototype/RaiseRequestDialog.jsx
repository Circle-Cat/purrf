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
  ACTION_LABELS,
  APPROVAL_ACTIONS,
} from "@/pages/MentorshipAdminPrototype/mockData";

const NO_PAIR = "none";

const RaiseRequestForm = ({ target, pending, onClose, onSave }) => {
  const actions = APPROVAL_ACTIONS.filter((a) =>
    (target.actions ?? APPROVAL_ACTIONS.map((x) => x.key)).includes(a.key),
  );
  const pairChoices = target.pairChoices ?? [];
  const [action, setAction] = useState(actions[0].key);
  const [pairId, setPairId] = useState(
    pairChoices.length === 1 ? String(pairChoices[0].pairId) : NO_PAIR,
  );
  const [reason, setReason] = useState("");

  const isPairAction =
    APPROVAL_ACTIONS.find((a) => a.key === action)?.target === "pair";
  const chosenPair =
    target.pairId ?? (pairId === NO_PAIR ? null : Number(pairId));
  const ready = reason.trim() && (!isPairAction || chosenPair);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Raise a change — {target.targetLabel}</DialogTitle>
        </DialogHeader>

        {pending.length > 0 ? (
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            Already waiting on a decision:{" "}
            {pending.map((r) => ACTION_LABELS[r.action]).join(", ")}. You can
            still raise another — the approver re-checks each one when deciding.
          </p>
        ) : null}

        {actions.length > 1 ? (
          <>
            <label className="text-xs text-slate-500">
              What are you asking for
            </label>
            <Select value={action} onValueChange={setAction}>
              <SelectTrigger className="text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {actions.map((a) => (
                  <SelectItem key={a.key} value={a.key}>
                    {a.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        ) : (
          <p className="text-sm font-medium">{actions[0].label}</p>
        )}

        {target.pairId == null && pairChoices.length > 0 ? (
          <>
            <label className="mt-2 text-xs text-slate-500">
              {isPairAction
                ? "Which pair"
                : "Which pair is this about (optional)"}
            </label>
            <Select value={pairId} onValueChange={setPairId}>
              <SelectTrigger className="text-sm">
                <SelectValue placeholder="Choose a pair" />
              </SelectTrigger>
              <SelectContent>
                {isPairAction ? null : (
                  <SelectItem value={NO_PAIR}>Not about one pair</SelectItem>
                )}
                {pairChoices.map((p) => (
                  <SelectItem key={p.pairId} value={String(p.pairId)}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        ) : null}

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
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!ready}
            onClick={() => onSave({ action, reason, pairId: chosenPair })}
          >
            Send for approval
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

/**
 * RaiseRequestDialog
 *
 * The entry for anything with consequences. Nothing here takes effect when you
 * press the button — it becomes a pending request, and somebody holding the
 * approve permission decides it.
 *
 * The request carries the pair it is about whenever there is one. That pair id
 * is what puts the decided note and the status change on the pair's own page;
 * a request raised without it would never show up there.
 *
 * Toggle "Approve" off in the header to see what the raiser sees afterwards:
 * the request is in the queue and the person's status has not moved.
 *
 * @returns {JSX.Element|null}
 */
const RaiseRequestDialog = ({ target, pending, onClose, onSave }) =>
  target ? (
    <RaiseRequestForm
      target={target}
      pending={pending}
      onClose={onClose}
      onSave={onSave}
    />
  ) : null;

export default RaiseRequestDialog;
