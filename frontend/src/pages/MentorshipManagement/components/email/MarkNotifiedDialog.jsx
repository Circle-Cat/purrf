import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { markNotified } from "@/api/mentorshipEmailApi";

// The backend refuses anything longer, as for any note.
const MAX_BODY_LENGTH = 5000;
const fieldClass = "w-full rounded-md border border-border p-2 text-sm";

/**
 * Records that a notification reached some people another way -- Teams,
 * Google Chat, a call -- one note each. People already notified of the
 * stage are skipped; for several people the dialog says how many first.
 * Nothing undoes it.
 *
 * @param {object} props
 * @param {boolean} props.open Whether the dialog is showing.
 * @param {(open: boolean) => void} props.onOpenChange Open/close handler.
 * @param {number|string} props.roundId The round.
 * @param {Array<{userId: number, name: string, notifiedStages: string[]}>} props.people
 *   Who to mark, with the stages each has already been notified of.
 * @param {Array<{value: string, label: string}>} props.stageOptions The
 *   notifications that can be marked for them.
 * @param {(result: {marked: number[], skipped: Object[]}) => void} props.onMarked
 *   Called after a successful mark.
 * @returns {JSX.Element}
 */
const MarkNotifiedDialog = ({
  open,
  onOpenChange,
  roundId,
  people,
  stageOptions,
  onMarked,
}) => {
  const [stage, setStage] = useState("");
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const single = people.length === 1;
  const trimmed = body.trim();
  const already = stage
    ? people.filter((p) => p.notifiedStages.includes(stage)).length
    : 0;
  const toMark = people.length - already;

  const reset = () => {
    setStage("");
    setBody("");
  };
  const changeOpen = (next) => {
    if (saving) return;
    if (!next) reset();
    onOpenChange(next);
  };

  const save = async () => {
    setSaving(true);
    try {
      const result = await markNotified(roundId, {
        userIds: people.map((p) => p.userId),
        stage,
        body: trimmed,
      });
      const skipped = result.skipped.length;
      toast.success(
        `Marked ${result.marked.length} as notified${skipped ? `, ${skipped} skipped` : ""}`,
      );
      reset();
      onOpenChange(false);
      onMarked(result);
    } catch (err) {
      toast.error(
        err?.response?.data?.message ??
          "Couldn't mark them as notified. Please try again.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {single
              ? `Mark as notified — ${people[0].name}`
              : `Mark ${people.length} people as notified`}
          </DialogTitle>
          <DialogDescription>
            Purrf did not send this one, so this note is the only record that it
            went out — say where and when. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1">
          <Label htmlFor="mark-notified-stage">Which notification</Label>
          <select
            id="mark-notified-stage"
            className={fieldClass}
            value={stage}
            onChange={(e) => setStage(e.target.value)}
            disabled={saving}
          >
            <option value="">Select a notification…</option>
            {stageOptions.map(({ value, label }) => {
              const reached =
                single && people[0].notifiedStages.includes(value);
              return (
                <option key={value} value={value} disabled={reached}>
                  {reached ? `${label} (already notified)` : label}
                </option>
              );
            })}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="mark-notified-body">How it was sent</Label>
          <Textarea
            id="mark-notified-body"
            value={body}
            maxLength={MAX_BODY_LENGTH}
            placeholder="Sent on Teams. No reply yet."
            onChange={(e) => setBody(e.target.value)}
            rows={4}
            disabled={saving}
          />
        </div>
        {!single && stage && already > 0 && (
          <p className="text-sm text-muted-foreground">
            {`${already} of ${people.length} already notified for this stage — they will be skipped`}
          </p>
        )}
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => changeOpen(false)}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            onClick={save}
            disabled={saving || !stage || trimmed === "" || toMark === 0}
          >
            {`Mark as notified · ${toMark}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default MarkNotifiedDialog;
