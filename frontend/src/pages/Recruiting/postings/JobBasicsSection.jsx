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
 * @param {{title: string, description: string, kind: string,
 *          onChange: (patch: object) => void}} props
 */
const JobBasicsSection = ({ title, description, kind, onChange }) => (
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
      <Select value={kind} onValueChange={(v) => onChange({ kind: v })}>
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
  </div>
);

export default JobBasicsSection;
