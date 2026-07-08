import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/**
 * Title / description / kind fields for a posting.
 *
 * `kindLocked`, when true, disables the Kind and Mentorship role selects —
 * both are only editable while a posting is still a draft; the caller
 * decides when that applies (see `PostingEditor`).
 *
 * @param {{title: string, description: string, kind: string, cooldownDays: (number|null|undefined),
 *          mentorshipRole: (string|null|undefined), kindLocked?: boolean,
 *          onChange: (patch: object) => void}} props
 */
const JobBasicsSection = ({
  title,
  description,
  kind,
  cooldownDays,
  mentorshipRole,
  kindLocked = false,
  onChange,
}) => (
  <div className="space-y-3">
    <div className="space-y-1">
      <Label htmlFor="posting-title">Title</Label>
      <Input
        id="posting-title"
        aria-label="Title"
        value={title ?? ""}
        onChange={(e) => onChange({ title: e.target.value })}
      />
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
      <Label htmlFor="posting-kind">Kind</Label>
      <Select
        value={kind}
        onValueChange={(v) => onChange({ kind: v })}
        disabled={kindLocked}
      >
        <SelectTrigger
          id="posting-kind"
          aria-label="Kind"
          className="w-full max-w-xs"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="activity">Activity</SelectItem>
          <SelectItem value="employment">Employment</SelectItem>
        </SelectContent>
      </Select>
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
        className="w-full max-w-xs"
        value={cooldownDays ?? ""}
        onChange={(e) =>
          onChange({
            cooldownDays: e.target.value ? Number(e.target.value) : null,
          })
        }
      />
    </div>
  </div>
);

export default JobBasicsSection;
