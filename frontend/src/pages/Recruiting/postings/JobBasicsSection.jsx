import { Input } from "@/components/ui/input";
import TermHint from "@/pages/Recruiting/components/TermHint";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import FieldError from "@/components/common/FieldError";
import { errorBorder } from "@/components/common/fieldErrors";
import { basicsKey } from "@/pages/Recruiting/postings/postingValidation";

/**
 * What each posting type means, shown under the picker. "Kind" is the stored
 * field name; the form calls it "Posting type" because the bare enum word
 * says nothing about which of the two an author wants.
 */
const KIND_HINTS = {
  activity: "An open program people apply to join.",
  employment: "Hiring a team member.",
};

/**
 * Title / description / posting-type fields for a posting.
 *
 * `kindLocked`, when true, disables the Posting type and Mentorship role selects —
 * both are only editable while a posting is still a draft; the caller
 * decides when that applies (see `PostingEditor`).
 *
 * @param {{title: string, description: string, kind: string, cooldownDays: (number|null|undefined),
 *          mentorshipRole: (string|null|undefined), kindLocked?: boolean,
 *          onChange: (patch: object) => void,
 *          errors?: Record<string, string>}} props
 */
const JobBasicsSection = ({
  title,
  description,
  kind,
  cooldownDays,
  mentorshipRole,
  kindLocked = false,
  onChange,
  errors = {},
}) => (
  <div className="space-y-3">
    <p className="text-sm font-medium text-slate-700">
      <TermHint id="editor.basics" />
    </p>
    <div className="space-y-1">
      <Label htmlFor="posting-title">Title</Label>
      <Input
        id="posting-title"
        aria-label="Title"
        className={errorBorder(errors, basicsKey("title")).trim()}
        value={title ?? ""}
        onChange={(e) => onChange({ title: e.target.value })}
      />
      <FieldError errors={errors} errorKey={basicsKey("title")} />
    </div>
    <div className="space-y-1">
      <Label htmlFor="posting-desc">Description</Label>
      <Textarea
        id="posting-desc"
        aria-label="Description"
        value={description ?? ""}
        onChange={(e) => onChange({ description: e.target.value })}
      />
    </div>
    <div className="space-y-1">
      <Label htmlFor="posting-kind">Posting type</Label>
      <Select
        value={kind}
        // Mentorship role only exists for an activity, and its select stops
        // rendering below the moment this changes. Left in place it would ride
        // along into the saved posting as a value nobody can see or reach.
        onValueChange={(v) =>
          onChange(
            v === "activity" ? { kind: v } : { kind: v, mentorshipRole: null },
          )
        }
        disabled={kindLocked}
      >
        <SelectTrigger
          id="posting-kind"
          aria-label="Posting type"
          className="w-full max-w-xs"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="activity">Activity</SelectItem>
          <SelectItem value="employment">Employment</SelectItem>
        </SelectContent>
      </Select>
      {KIND_HINTS[kind] && (
        <p className="text-sm text-slate-500">{KIND_HINTS[kind]}</p>
      )}
    </div>
    {kind === "activity" && (
      <div className="space-y-1">
        <Label htmlFor="posting-mentorship-role">Mentorship role</Label>
        <Select
          value={mentorshipRole ?? "none"}
          onValueChange={(v) =>
            onChange({ mentorshipRole: v === "none" ? null : v })
          }
          disabled={kindLocked}
        >
          <SelectTrigger
            id="posting-mentorship-role"
            aria-label="Mentorship role"
            className="w-full max-w-xs"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">None</SelectItem>
            <SelectItem value="mentor">Mentor</SelectItem>
            <SelectItem value="mentee">Mentee</SelectItem>
          </SelectContent>
        </Select>
      </div>
    )}
    <div className="space-y-1">
      <Label htmlFor="posting-cooldown">Cooldown days</Label>
      <Input
        id="posting-cooldown"
        type="number"
        min={0}
        aria-label="Cooldown days"
        className={`w-full max-w-xs${errorBorder(errors, basicsKey("cooldownDays"))}`}
        value={cooldownDays ?? ""}
        onChange={(e) =>
          onChange({
            cooldownDays: e.target.value ? Number(e.target.value) : null,
          })
        }
      />
      <FieldError errors={errors} errorKey={basicsKey("cooldownDays")} />
    </div>
  </div>
);

export default JobBasicsSection;
