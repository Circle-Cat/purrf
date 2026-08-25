import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/**
 * AdjustBalanceDialog
 *
 * Writes one correction to one person's ledger.
 *
 * Opened from a row, so the person is already chosen -- there is no name
 * picker here, and no way to correct the wrong ledger by mistyping an id.
 *
 * The ledger only ever grows: a correction cannot be edited or taken back,
 * only followed by another one. So this asks for confirmation with the figures
 * spelled out, and afterwards shows the balance the server computed rather
 * than one added up here. Nothing on the server dedupes corrections, so that
 * returned figure is the only way to tell whether a second click landed.
 *
 * Hours are typed as a signed decimal string and sent as typed. Negative is
 * the normal case at launch -- leave already taken this year arrives as
 * negative hours, because a request cannot be dated in the past.
 *
 * @param {{
 *   person: object|null,
 *   isSaving: boolean,
 *   saveError: string|null,
 *   result: object|null,
 *   onClose: () => void,
 *   onSubmit: (payload: object) => Promise<boolean>,
 * }} props
 */
const AdjustBalanceDialog = ({
  person,
  isSaving,
  saveError,
  result,
  onClose,
  onSubmit,
}) => {
  const [hours, setHours] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [note, setNote] = useState("");
  const [problem, setProblem] = useState(null);
  const [isConfirming, setIsConfirming] = useState(false);

  useEffect(() => {
    if (person) {
      setHours("");
      setEffectiveDate("");
      setNote("");
      setProblem(null);
      setIsConfirming(false);
    }
  }, [person]);

  if (!person) return null;

  const submit = async () => {
    // Only what this form can see. A date in the future, a note of nothing, a
    // person who does not exist: all refused by the server in its own words.
    if (!hours.trim() || !effectiveDate) {
      setProblem("Give the hours and the date they take effect.");
      setIsConfirming(false);
      return;
    }
    setProblem(null);
    setIsConfirming(false);
    await onSubmit({
      userId: person.userId,
      hours: hours.trim(),
      effectiveDate,
      note,
    });
  };

  const name = person.name || person.ldap;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{`Correct ${name}'s balance`}</DialogTitle>
        </DialogHeader>

        {result ? (
          <div className="space-y-2">
            {/* The figure the server computed. Adding it up here would let the
                screen and the ledger disagree about what was just written. */}
            <p className="text-sm">
              {`Wrote ${result.hours} h dated ${result.effectiveDate}.`}
            </p>
            <p className="text-base font-semibold tabular-nums">
              {`${name}'s balance is now ${result.balanceHours} h`}
            </p>
            <p className="text-sm text-muted-foreground">
              Corrections cannot be edited or taken back — a mistake is followed
              by another correction.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {`Holding ${person.balanceHours} h now.`}
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="adjust-hours">Hours</Label>
                <Input
                  id="adjust-hours"
                  value={hours}
                  placeholder="-8.00"
                  disabled={isSaving}
                  onChange={(event) => setHours(event.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="adjust-date">Effective date</Label>
                <Input
                  id="adjust-date"
                  type="date"
                  value={effectiveDate}
                  disabled={isSaving}
                  onChange={(event) => setEffectiveDate(event.target.value)}
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="adjust-note">Note</Label>
              <Textarea
                id="adjust-note"
                value={note}
                rows={3}
                disabled={isSaving}
                onChange={(event) => setNote(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                The note is the only thing that tells a later reader what this
                correction was for.
              </p>
            </div>

            {problem && <p className="text-sm text-red-700">{problem}</p>}
            {saveError && <p className="text-sm text-red-700">{saveError}</p>}
          </div>
        )}

        <DialogFooter>
          {result ? (
            <Button onClick={onClose}>Done</Button>
          ) : isConfirming ? (
            <>
              <span className="mr-auto text-sm text-muted-foreground">
                {`Write ${hours || "—"} h to ${name}? This cannot be undone.`}
              </span>
              <Button
                variant="outline"
                disabled={isSaving}
                onClick={() => setIsConfirming(false)}
              >
                Cancel
              </Button>
              <Button disabled={isSaving} onClick={submit}>
                {isSaving ? "Writing…" : "Yes, write it"}
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" disabled={isSaving} onClick={onClose}>
                Cancel
              </Button>
              <Button disabled={isSaving} onClick={() => setIsConfirming(true)}>
                Write the correction
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AdjustBalanceDialog;
