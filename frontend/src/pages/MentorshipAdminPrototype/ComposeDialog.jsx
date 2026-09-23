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
import { EMAIL_TEMPLATES } from "@/pages/MentorshipAdminPrototype/mockData";

/** Placeholder bodies. Real wording comes from the business side, verbatim. */
const PREVIEW = {
  mentorship_round_recruitment: (name) =>
    `Dear ${name},\n\nRegistration for the next mentorship round is open. Sign in to Purrf and register as a mentor or mentee before the deadline.\n\n[PLACEHOLDER — the real wording comes from the business side.]`,
  mentorship_midterm_reminder: (name) =>
    `Dear ${name},\n\nYou have logged 0 of 5 meetings for this round. Please sign in to Purrf and record the date and time of any meetings you have already held.\n\nIf anything is getting in the way, reply to this email and let us know.`,
  mentorship_first_contact_reminder: (name) =>
    `Dear ${name},\n\nOur records show you have not yet contacted your mentor. The deadline is 2026-09-19.\n\nPlease email them to arrange your first meeting, and copy mentorship-outreach@circlecat.org so we can mark this step complete.`,
};

const fallback = (name) =>
  `Dear ${name},\n\n[PLACEHOLDER — the real wording comes from the business side and is copied in verbatim.]`;

/**
 * ComposeDialog
 *
 * Sending always picks a template; the template key is what later answers
 * "has this person had the mid-term reminder yet?".
 *
 * The preview is the trap worth showing: a template carrying per-recipient
 * values renders differently for all thirty people, and one preview box can
 * only show one of them. Saying whose it is stops the sender assuming everyone
 * gets the text on screen.
 *
 * `target.recipients` are `{ participantId, userId, roundId, name }` — someone
 * not yet registered has a user id and no participant id, and names the round
 * the message belongs to. Each one gets their own message, anchored on the
 * person and the round.
 *
 * @returns {JSX.Element|null}
 */
const ComposeDialog = ({ target, onClose, onSend }) => {
  const [template, setTemplate] = useState(null);
  if (!target) return null;
  const chosen =
    template ?? target.defaultTemplate ?? "mentorship_midterm_reminder";

  const recipients = target.recipients ?? [];
  const first = recipients[0]?.name ?? "there";
  const render = PREVIEW[chosen] ?? fallback;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            Send email — {recipients.length}{" "}
            {recipients.length === 1 ? "recipient" : "recipients"}
          </DialogTitle>
        </DialogHeader>

        <p className="text-xs text-slate-500">
          {recipients.map((r) => r.name).join(" · ")}
        </p>

        <label className="mt-2 text-xs text-slate-500">Template</label>
        <Select value={chosen} onValueChange={setTemplate}>
          <SelectTrigger className="text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {EMAIL_TEMPLATES.map((t) => (
              <SelectItem key={t.key} value={t.key}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <label className="mt-2 text-xs text-slate-500">
          Preview for {first}
          {recipients.length > 1
            ? ` — ${recipients.length - 1} others will get their own values`
            : ""}
        </label>
        <Textarea value={render(first)} readOnly rows={9} className="text-sm" />

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() =>
              onSend({
                templateKey: chosen,
                messages: recipients.map((r) => ({
                  participantId: r.participantId,
                  userId: r.userId,
                  roundId: r.roundId,
                  body: render(r.name),
                })),
              })
            }
          >
            Send {recipients.length}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ComposeDialog;
