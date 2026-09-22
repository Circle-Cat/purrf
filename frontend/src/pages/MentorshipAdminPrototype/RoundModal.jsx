import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * The timeline, as redesigned.
 *
 * The grammar of the original table is kept: one row per phase, the admin's
 * own date on the left and the participant's deadline on the right. Three
 * things changed.
 *
 *   - `training*` is renamed to `onboarding*`. Onboarding is the business
 *     concept; the training table is only where it is recorded.
 *   - The onboarding deadline became **required**, because it is now the gate:
 *     it is the round registration deadline as well.
 *   - The Matching row's participant deadline is `firstMeetingDeadlineAt`,
 *     which is the field that always meant "the mentee must have emailed their
 *     mentor by". `matchingCompletedAt` — internal matching finished — is not
 *     on this form at all: the service stamps it when a run is published.
 */
const PHASES = [
  {
    phase: "Sign-up",
    admin: { key: "promotionStartAt", label: "Date to send recruitment email" },
    deadlines: [
      {
        key: "mentorApplicationDeadlineAt",
        label: "Mentor job application deadline",
        required: true,
      },
      {
        key: "menteeApplicationDeadlineAt",
        label: "Mentee job application deadline",
        required: true,
      },
    ],
    adminRequired: true,
  },
  {
    phase: "Onboarding",
    admin: {
      key: "onboardingNotificationAt",
      label: "Date to send onboarding email",
    },
    deadlines: [
      {
        key: "onboardingDeadlineAt",
        label: "Complete onboarding — also the registration deadline",
        required: true,
      },
    ],
  },
  {
    phase: "Matching",
    admin: {
      key: "matchNotificationAt",
      label: "Date to publish matching email",
    },
    deadlines: [
      { key: "firstMeetingDeadlineAt", label: "First contact with mentor" },
    ],
    adminRequired: true,
  },
  {
    phase: "Reminder",
    admin: { key: "meetingLogReminderAt", label: "Mid-term reminder email" },
    deadlines: [
      {
        key: "meetingsCompletionDeadlineAt",
        label: "Complete required meetings",
        required: true,
      },
    ],
  },
  {
    phase: "Feedback",
    admin: { key: "feedbackStartAt", label: "Send feedback email" },
    deadlines: [
      { key: "feedbackDeadlineAt", label: "Feedback submission deadline" },
    ],
  },
];

const EMPTY = {
  name: "",
  requiredMeetings: 5,
  timeline: Object.fromEntries(
    PHASES.flatMap((p) => [p.admin.key, ...p.deadlines.map((d) => d.key)]).map(
      (k) => [k, ""],
    ),
  ),
};

/**
 * RoundModal
 *
 * Create or edit a round. Every date on the left column is a *prompt* — a
 * reminder that today is the day to send something — not a trigger. Nothing on
 * this form schedules an email; every message in the console is sent by hand.
 *
 * @returns {JSX.Element|null}
 */
const RoundModal = ({ round, onClose, onSave }) => {
  const [form, setForm] = useState(EMPTY);

  useEffect(() => {
    if (!round) return;
    setForm({
      ...EMPTY,
      ...round,
      timeline: { ...EMPTY.timeline, ...(round.timeline ?? {}) },
    });
  }, [round]);

  if (!round) return null;

  const setDate = (key, value) =>
    setForm((f) => ({ ...f, timeline: { ...f.timeline, [key]: value } }));

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{round.id ? "Edit round" : "New round"}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-wrap gap-3">
          <div className="flex-1">
            <label className="text-xs text-slate-500">Round name</label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div className="w-40">
            <label className="text-xs text-slate-500">Required meetings</label>
            <Input
              type="number"
              value={form.requiredMeetings}
              onChange={(e) =>
                setForm({ ...form, requiredMeetings: Number(e.target.value) })
              }
            />
          </div>
        </div>

        <div className="mt-3 overflow-hidden rounded-md border border-slate-200">
          <div className="grid grid-cols-[7rem_1fr_1fr] gap-px bg-slate-200 text-xs font-medium">
            <div className="bg-slate-50 px-3 py-2">Phase</div>
            <div className="bg-slate-50 px-3 py-2">Admin action</div>
            <div className="bg-slate-50 px-3 py-2">Participant deadline</div>
          </div>
          {PHASES.map((p) => (
            <div
              key={p.phase}
              className="grid grid-cols-[7rem_1fr_1fr] gap-px border-t border-slate-200 bg-slate-200"
            >
              <div className="bg-white px-3 py-3 text-sm">{p.phase}</div>
              <div className="bg-white px-3 py-3">
                <label className="text-xs text-slate-500">
                  {p.admin.label}
                  {p.adminRequired ? " *" : ""}
                </label>
                <Input
                  type="date"
                  className="mt-1 h-8 text-sm"
                  value={form.timeline[p.admin.key] ?? ""}
                  onChange={(e) => setDate(p.admin.key, e.target.value)}
                />
              </div>
              <div className="space-y-2 bg-white px-3 py-3">
                {p.deadlines.map((d) => (
                  <div key={d.key}>
                    <label className="text-xs text-slate-500">
                      {d.label}
                      {d.required ? " *" : ""}
                    </label>
                    <Input
                      type="date"
                      className="mt-1 h-8 text-sm"
                      value={form.timeline[d.key] ?? ""}
                      onChange={(e) => setDate(d.key, e.target.value)}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <p className="text-xs text-slate-500">
          Dates in the Admin action column are prompts, not schedules. Nothing
          here sends anything — every message in this console goes out when
          somebody presses send.
        </p>
        <p className="text-xs text-slate-500">
          &ldquo;Internal matching finished&rdquo; is not on this form: the
          service stamps it when a matching run is published, so there is
          nothing for an admin to type.
        </p>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => onSave({ ...form, id: round.id })}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default RoundModal;
