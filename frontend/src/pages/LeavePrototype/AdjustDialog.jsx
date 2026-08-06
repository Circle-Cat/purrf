import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
 * doing it.
 *
 * Granting the hand-issued half of the extra leave before a holiday and
 * correcting one person's balance were separate screens, which was two ways to
 * do one thing. They differ in exactly two respects, so those are the two
 * controls: who it lands on, and whether it draws down that person's holiday
 * allowance for the year. The note is required either way, because a
 * hand-written balance change without a stated reason is the one entry nobody
 * can reconstruct later.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {object|null} props.person - preselected target, null for a region grant
 * @param {Array<object>} props.people - everyone, for resolving region scope
 * @param {(id: number) => number} props.balanceOf
 * @param {(id: number) => number} props.allowanceUsedBy
 * @param {(region: string) => number} props.allowanceFor
 * @param {(rows: Array<object>, countsAgainstAllowance: boolean) => void} props.onSubmit
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
  const [scope, setScope] = useState("person");
  const [hours, setHours] = useState("");
  const [note, setNote] = useState("");
  const [fromAllowance, setFromAllowance] = useState(false);

  const reset = () => {
    setScope(person ? "person" : "region:CN");
    setHours("");
    setNote("");
    setFromAllowance(false);
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

  // Opened from the region button there is nobody preselected, and "this
  // person" is not on the menu — fall back rather than showing an empty box.
  const effectiveScope = scope === "person" && !person ? "region:CN" : scope;

  const targets =
    effectiveScope === "person"
      ? [person]
      : people.filter((p) => p.region === effectiveScope.slice(7));

  const region =
    effectiveScope === "person" ? person?.region : effectiveScope.slice(7);
  const allowance = region ? allowanceFor(region) : 0;

  /** Least headroom among the targets — the one that would overrun first. */
  const remaining = targets.length
    ? Math.min(...targets.map((p) => allowance - allowanceUsedBy(p.id)))
    : 0;
  const uniform = new Set(targets.map((p) => allowanceUsedBy(p.id))).size <= 1;

  const overruns = fromAllowance && entered && delta > remaining;
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
        entryType: fromAllowance ? "holiday_grant" : "manual_adjustment",
        hours: delta,
        note: note.trim(),
        effectiveDate: today(),
      })),
      fromAllowance,
    );
    close();
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && close()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Write a ledger entry</DialogTitle>
          <DialogDescription>
            Existing rows are never edited — a correction is another row.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="space-y-1.5">
            <Label htmlFor="adjust-scope">Applies to</Label>
            <Select value={effectiveScope} onValueChange={setScope}>
              <SelectTrigger id="adjust-scope">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {person && (
                  <SelectItem value="person">{person.name}</SelectItem>
                )}
                {Object.entries(REGIONS).map(([key, r]) => (
                  <SelectItem key={key} value={`region:${key}`}>
                    Everyone in {r.label} (
                    {people.filter((p) => p.region === key).length})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

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

          <label className="flex items-start gap-2.5 cursor-pointer">
            <Checkbox
              checked={fromAllowance}
              className="mt-0.5"
              onCheckedChange={(v) => setFromAllowance(Boolean(v))}
            />
            <span className="text-sm text-slate-700">
              Counts against the holiday allowance
              <span className="block text-xs text-slate-500">
                Tick this when issuing the hand-granted half of the extra leave
                before a holiday. Leave it clear for a plain correction, which
                does not touch the allowance.
              </span>
            </span>
          </label>

          {/* What lands where */}
          <p className="text-xs text-slate-500 tabular-nums">
            {effectiveScope === "person" && person
              ? `Currently ${balanceOf(person.id).toFixed(2)}h.${
                  entered && delta !== 0
                    ? ` Leaves them at ${(balanceOf(person.id) + delta).toFixed(2)}h, unless something else moves it first.`
                    : ""
                }`
              : `Writes one row for each of ${targets.length} ${targets.length === 1 ? "person" : "people"}.`}
          </p>

          {fromAllowance && region && (
            <p className="text-xs text-slate-500 tabular-nums">
              Allowance {allowance.toFixed(2)}h a year.{" "}
              {uniform
                ? `${remaining.toFixed(2)}h left.`
                : `As little as ${remaining.toFixed(2)}h left for some of them.`}
            </p>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="adjust-note">Note</Label>
            <Textarea
              id="adjust-note"
              rows={2}
              value={note}
              placeholder={
                fromAllowance
                  ? "Spring Festival"
                  : "Why this correction exists."
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
            Write {targets.length > 1 ? `${targets.length} entries` : "entry"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AdjustDialog;
