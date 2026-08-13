import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { today } from "@/pages/LeavePrototype/leaveCalc";

/**
 * AdjustDialog
 *
 * Writes a ledger row by hand — the only way hours move without the engine
 * doing it, and always for one person at a time. There is no bulk path: the
 * yearly entitlement accrues on its own, and everything else is a correction
 * somebody has to justify individually.
 *
 * The opening balance carried over at go-live is written here too, with the
 * note saying where the number came from. It needs no type of its own.
 *
 * The note is required: a hand-written balance change with no stated reason is
 * the one entry nobody can reconstruct later.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {object|null} props.person - whose balance is being corrected
 * @param {(id: number) => number} props.balanceOf
 * @param {(rows: Array<object>) => void} props.onSubmit
 * @returns {JSX.Element}
 */
const AdjustDialog = ({ open, onOpenChange, person, balanceOf, onSubmit }) => {
  const [hours, setHours] = useState("");
  const [note, setNote] = useState("");

  const reset = () => {
    setHours("");
    setNote("");
  };

  const close = () => {
    reset();
    onOpenChange(false);
  };

  // What is typed is what is stored. Every ledger row is a signed number of
  // hours, so asking for the change rather than the intended total means no
  // arithmetic happens between the box and the database — and no row derived
  // from a balance that moved while the dialog was open.
  const delta = Number(hours);
  const entered = hours !== "" && !Number.isNaN(delta);

  const canSubmit =
    Boolean(person) && entered && delta !== 0 && note.trim().length > 0;

  const submit = () => {
    if (!canSubmit) return;
    onSubmit([
      {
        id: Date.now(),
        personId: person.id,
        personName: person.name,
        entryType: "manual_adjustment",
        hours: delta,
        note: note.trim(),
        effectiveDate: today(),
      },
    ]);
    close();
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && close()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Adjust {person?.name}</DialogTitle>
          <DialogDescription>
            Corrects this person's balance and nothing else. Nobody else is
            touched, and the yearly accrual carries on unchanged.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="space-y-1.5">
            <Label htmlFor="adjust-hours">Add or subtract</Label>
            <Input
              id="adjust-hours"
              type="number"
              step="0.25"
              value={hours}
              placeholder="8 or -4"
              onChange={(e) => setHours(e.target.value)}
            />
          </div>

          {person && (
            <p className="text-xs text-slate-500 tabular-nums">
              Currently {balanceOf(person.id).toFixed(2)}h.
              {entered && delta !== 0
                ? ` Leaves them at ${(balanceOf(person.id) + delta).toFixed(2)}h, unless something else moves it first.`
                : ""}
            </p>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="adjust-note">Note</Label>
            <Textarea
              id="adjust-note"
              rows={2}
              value={note}
              placeholder="Why this correction exists."
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!canSubmit}>
            Write entry
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AdjustDialog;
