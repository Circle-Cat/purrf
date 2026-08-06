import { useState } from "react";
import { AlertTriangle } from "lucide-react";
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
import { REGIONS } from "@/pages/LeavePrototype/mockData";
import { today } from "@/pages/LeavePrototype/leaveCalc";

/**
 * AdjustDialog
 *
 * Writes ledger rows by hand — the only way hours move without the engine
 * doing it. Two jobs, told apart by where it was opened from rather than by a
 * control inside it:
 *
 *   from a person's row    a correction to that person, touching nothing else
 *   from the grant button  issues holiday allowance to a whole region at once
 *
 * There is no scope selector, because the entry point already answered that
 * question and offering it again only creates a way to answer it differently
 * by accident.
 *
 * The note is required either way: a hand-written balance change with no
 * stated reason is the one entry nobody can reconstruct later.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {object|null} props.person - set for a correction, null for a grant
 * @param {Array<object>} props.people - everyone, for resolving a region
 * @param {(id: number) => number} props.balanceOf
 * @param {(id: number) => number} props.allowanceUsedBy
 * @param {(region: string) => number} props.allowanceFor
 * @param {(rows: Array<object>, isGrant: boolean) => void} props.onSubmit
 * @returns {JSX.Element}
 */
const AdjustDialog = ({
  open,
  onOpenChange,
  person,
  people,
  balanceOf,
  allowanceUsedBy,
  allowanceFor,
  onSubmit,
}) => {
  const [region, setRegion] = useState("CN");
  const [hours, setHours] = useState("");
  const [note, setNote] = useState("");

  const isGrant = !person;

  const reset = () => {
    setRegion("CN");
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

  const targets = isGrant
    ? people.filter((p) => p.region === region)
    : [person];

  const allowance = isGrant ? allowanceFor(region) : 0;

  /** Least headroom among the targets — whoever would run out first. */
  const remaining = targets.length
    ? Math.min(...targets.map((p) => allowance - allowanceUsedBy(p.id)))
    : 0;
  const uniform = new Set(targets.map((p) => allowanceUsedBy(p.id))).size <= 1;

  const overruns = isGrant && entered && delta > remaining;
  const canSubmit =
    entered && delta !== 0 && note.trim().length > 0 && targets.length > 0;

  const submit = () => {
    if (!canSubmit) return;
    const stamp = Date.now();
    onSubmit(
      targets.map((p, i) => ({
        id: stamp + i,
        personId: p.id,
        personName: p.name,
        entryType: isGrant ? "holiday_grant" : "manual_adjustment",
        hours: delta,
        note: note.trim(),
        effectiveDate: today(),
      })),
      isGrant,
    );
    close();
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && close()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {isGrant ? "Grant holiday allowance" : `Adjust ${person.name}`}
          </DialogTitle>
          <DialogDescription>
            {isGrant
              ? "Hands out part of this year's holiday allowance to a whole region at once. Issue it before the holiday it covers."
              : "Corrects this person's balance and nothing else. Their holiday allowance is untouched."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          {isGrant && (
            <div className="space-y-1.5">
              <Label htmlFor="grant-region">Region</Label>
              <Select value={region} onValueChange={setRegion}>
                <SelectTrigger id="grant-region">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(REGIONS).map(([key, r]) => (
                    <SelectItem key={key} value={key}>
                      {r.label} ({people.filter((p) => p.region === key).length}{" "}
                      people)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* The allowance is the whole point of a grant, so it is stated
              before the amount rather than annotated after it. */}
          {isGrant &&
            (allowance === 0 ? (
              <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-sm text-slate-600">
                {REGIONS[region].label} has no holiday allowance — all of its
                extra leave accrues weekly instead. Nothing to grant here.
              </div>
            ) : (
              <div className="rounded-lg bg-slate-50 border border-slate-200 p-3">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm text-slate-700">
                    Holiday allowance this year
                  </span>
                  <span className="text-sm tabular-nums text-slate-500">
                    {allowance.toFixed(2)}h each
                  </span>
                </div>
                <div className="flex items-baseline justify-between gap-3 mt-1">
                  <span className="text-sm font-medium text-slate-900">
                    {uniform ? "Left to give" : "Left for whoever has least"}
                  </span>
                  <span
                    className={`text-sm font-semibold tabular-nums ${
                      remaining <= 0 ? "text-rose-600" : "text-slate-900"
                    }`}
                  >
                    {remaining.toFixed(2)}h
                  </span>
                </div>
              </div>
            ))}

          <div className="space-y-1.5">
            <Label htmlFor="adjust-hours">
              {isGrant ? "Grant to each person" : "Add or subtract"}
            </Label>
            <Input
              id="adjust-hours"
              type="number"
              step="0.25"
              value={hours}
              placeholder={isGrant ? "8" : "8 or -4"}
              onChange={(e) => setHours(e.target.value)}
            />
          </div>

          <p className="text-xs text-slate-500 tabular-nums">
            {isGrant
              ? `Writes one row for each of ${targets.length} ${targets.length === 1 ? "person" : "people"}.`
              : `Currently ${balanceOf(person.id).toFixed(2)}h.${
                  entered && delta !== 0
                    ? ` Leaves them at ${(balanceOf(person.id) + delta).toFixed(2)}h, unless something else moves it first.`
                    : ""
                }`}
          </p>

          <div className="space-y-1.5">
            <Label htmlFor="adjust-note">Note</Label>
            <Textarea
              id="adjust-note"
              rows={2}
              value={note}
              placeholder={
                isGrant ? "Spring Festival" : "Why this correction exists."
              }
              onChange={(e) => setNote(e.target.value)}
            />
          </div>

          {overruns && (
            <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              <p>
                Only {remaining.toFixed(2)}h of allowance left, so {delta}h
                takes at least one person over for the year. Allowed — you may
                have a reason — but nothing else will flag it.
              </p>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!canSubmit}>
            {isGrant && targets.length !== 1
              ? `Grant to ${targets.length}`
              : "Write entry"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AdjustDialog;
