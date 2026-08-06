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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { today } from "@/pages/LeavePrototype/leaveCalc";

/**
 * AdjustDialog
 *
 * Write a ledger row by hand against one person.
 *
 * Opened from that person's row in the balances table, so there is no picker
 * to get wrong. The note is required — a hand-written balance change with no
 * stated reason is the one entry nobody can reconstruct later.
 *
 * @param {object} props
 * @param {object|null} props.person - null when closed
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {boolean} props.hasOpeningBalance - whether this person already has one
 * @param {(row: object) => void} props.onSubmit
 * @returns {JSX.Element}
 */
const AdjustDialog = ({
  person,
  onOpenChange,
  hasOpeningBalance,
  onSubmit,
}) => {
  const [entryType, setEntryType] = useState("manual_adjustment");
  const [hours, setHours] = useState("");
  const [note, setNote] = useState("");

  const reset = () => {
    setEntryType("manual_adjustment");
    setHours("");
    setNote("");
  };

  const close = () => {
    reset();
    onOpenChange(false);
  };

  const parsed = Number(hours);
  const hoursValid = hours !== "" && !Number.isNaN(parsed) && parsed !== 0;
  const duplicateOpening = entryType === "opening_balance" && hasOpeningBalance;
  const canSubmit = hoursValid && note.trim().length > 0 && !duplicateOpening;

  const submit = () => {
    if (!canSubmit || !person) return;
    onSubmit({
      id: Date.now(),
      personId: person.id,
      personName: person.name,
      entryType,
      hours: parsed,
      note: note.trim(),
      effectiveDate: today(),
    });
    close();
  };

  return (
    <Dialog open={Boolean(person)} onOpenChange={(next) => !next && close()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Adjust {person?.name}</DialogTitle>
          <DialogDescription>
            Writes a new ledger row. Existing rows are never edited — a
            correction is another row.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="adjust-type">Type</Label>
              <Select value={entryType} onValueChange={setEntryType}>
                <SelectTrigger id="adjust-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="manual_adjustment">Adjustment</SelectItem>
                  <SelectItem value="opening_balance">
                    Opening balance
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="adjust-hours">Hours</Label>
              <Input
                id="adjust-hours"
                type="number"
                step="0.25"
                value={hours}
                placeholder="-4 or 12.5"
                onChange={(e) => setHours(e.target.value)}
              />
            </div>
          </div>

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

          {entryType === "opening_balance" && !duplicateOpening && (
            <p className="text-xs text-slate-500">
              What this person had before the system went live. One per person,
              and the accrual engine ignores it when working out what is still
              owed.
            </p>
          )}

          {duplicateOpening && (
            <p className="text-xs text-rose-600">
              {person?.name} already has an opening balance. Use an adjustment
              instead.
            </p>
          )}
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
