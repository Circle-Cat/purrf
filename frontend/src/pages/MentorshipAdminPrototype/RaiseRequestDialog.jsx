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
  ACTION_LABELS,
  APPROVAL_ACTIONS,
  APPROVE_HOLDERS,
} from "@/pages/MentorshipAdminPrototype/mockData";

const NO_PAIR = "none";

const RaiseRequestForm = ({ target, pending, viewerId, onClose, onSave }) => {
  const actions = APPROVAL_ACTIONS.filter((a) =>
    (target.actions ?? APPROVAL_ACTIONS.map((x) => x.key)).includes(a.key),
  );
  const [action, setAction] = useState(actions[0].key);
  const isPairAction =
    APPROVAL_ACTIONS.find((a) => a.key === action)?.target === "pair";
  // A partner change can only end a pair that is still going; anything else
  // may be about an ended one too.
  const pairChoices = (target.pairChoices ?? []).filter(
    (p) => !isPairAction || p.active,
  );
  const [pairId, setPairId] = useState(NO_PAIR);
  const onlyPair = pairChoices.length === 1 ? pairChoices[0].pairId : null;
  const [reason, setReason] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  const reviewers = APPROVE_HOLDERS.filter((h) => h.userId !== viewerId);

  const chosenPair =
    target.pairId ??
    (pairId !== NO_PAIR && pairChoices.some((p) => String(p.pairId) === pairId)
      ? Number(pairId)
      : isPairAction
        ? onlyPair
        : null);
  const ready = reason.trim() && reviewerId && (!isPairAction || chosenPair);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Change status / flag — {target.targetLabel}</DialogTitle>
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
            <label className="text-xs text-slate-500" htmlFor="approval-action">
              What are you asking for
            </label>
            <select
              id="approval-action"
              className="w-full rounded-md border border-slate-300 p-2 text-sm"
              value={action}
              onChange={(e) => setAction(e.target.value)}
            >
              {actions.map((a) => (
                <option key={a.key} value={a.key}>
                  {a.label}
                </option>
              ))}
            </select>
          </>
        ) : (
          <p className="text-sm font-medium">{actions[0].label}</p>
        )}

        {target.pairId == null && pairChoices.length > 0 ? (
          <>
            <label
              className="mt-2 text-xs text-slate-500"
              htmlFor="approval-pair"
            >
              {isPairAction
                ? "Which pair"
                : "Which pair is this about (optional)"}
            </label>
            <select
              id="approval-pair"
              className="w-full rounded-md border border-slate-300 p-2 text-sm"
              value={chosenPair == null ? NO_PAIR : String(chosenPair)}
              onChange={(e) => setPairId(e.target.value)}
            >
              <option value={NO_PAIR}>
                {isPairAction ? "Choose a pair…" : "Not about one pair"}
              </option>
              {pairChoices.map((p) => (
                <option key={p.pairId} value={String(p.pairId)}>
                  {p.label}
                </option>
              ))}
            </select>
          </>
        ) : null}

        <label
          className="mt-2 text-xs text-slate-500"
          htmlFor="approval-reviewer"
        >
          Reviewer
        </label>
        <select
          id="approval-reviewer"
          className="w-full rounded-md border border-slate-300 p-2 text-sm"
          value={reviewerId}
          onChange={(e) => setReviewerId(e.target.value)}
        >
          <option value="">Select a reviewer…</option>
          {reviewers.map((h) => (
            <option key={h.userId} value={h.userId}>
              {h.name} ({h.email})
            </option>
          ))}
        </select>
        <p className="text-xs text-slate-500">
          It is sent to this person, but anyone holding the approve permission
          can decide it — except you.
        </p>

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
            onClick={() =>
              onSave({
                action,
                reason,
                pairId: chosenPair,
                reviewerId: Number(reviewerId),
              })
            }
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
const RaiseRequestDialog = ({ target, pending, viewerId, onClose, onSave }) =>
  target ? (
    <RaiseRequestForm
      target={target}
      pending={pending}
      viewerId={viewerId}
      onClose={onClose}
      onSave={onSave}
    />
  ) : null;

export default RaiseRequestDialog;
