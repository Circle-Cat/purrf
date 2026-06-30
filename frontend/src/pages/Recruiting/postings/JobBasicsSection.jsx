import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

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
        value={title}
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
      <select
        id="posting-kind"
        aria-label="Kind"
        className="h-9 rounded-md border border-slate-300 px-2 text-sm"
        value={kind}
        onChange={(e) => onChange({ kind: e.target.value })}
      >
        <option value="activity">Activity</option>
        <option value="employment">Employment</option>
      </select>
    </div>
  </div>
);

export default JobBasicsSection;
