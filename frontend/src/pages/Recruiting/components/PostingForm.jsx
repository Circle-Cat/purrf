import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";

/** Pipeline stages selectable for a posting (backend ApplicationStage subset). */
const STAGES = [
  { value: "recruiter_screening", label: "Recruiter screening" },
  { value: "behavioral", label: "Behavioral" },
  { value: "tech", label: "Tech" },
  { value: "board_review", label: "Board review" },
];

const KINDS = ["activity", "employment"];

/**
 * Minimal create/edit posting dialog. Pass `job` to edit, null to create.
 *
 * @param {{open: boolean, job: object|null, onSubmit: Function,
 *          onOpenChange: Function}} props
 */
const PostingForm = ({ open, job, onSubmit, onOpenChange }) => {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState("activity");
  const [stages, setStages] = useState([]);
  const [schemaText, setSchemaText] = useState("");
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!open) return;
    setTitle(job?.title ?? "");
    setDescription(job?.description ?? "");
    setKind(job?.kind ?? "activity");
    setStages((job?.pipelineConfig ?? []).map((s) => s.stage));
    setSchemaText(
      job?.formSchema ? JSON.stringify(job.formSchema, null, 2) : "",
    );
    setErrors({});
  }, [open, job]);

  const toggleStage = (value) =>
    setStages((prev) =>
      prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value],
    );

  const handleSave = () => {
    const next = {};
    if (!title.trim()) next.title = "Title is required";
    let formSchema = null;
    if (schemaText.trim()) {
      try {
        formSchema = JSON.parse(schemaText);
      } catch {
        next.schema = "Form schema must be valid JSON";
      }
    }
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    onSubmit({
      title: title.trim(),
      description: description.trim() || null,
      kind,
      pipelineConfig: STAGES.filter((s) => stages.includes(s.value)).map(
        (s) => ({
          stage: s.value,
        }),
      ),
      formSchema,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{job ? "Edit posting" : "New posting"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            {errors.title && (
              <p className="text-xs text-red-600">{errors.title}</p>
            )}
          </div>
          <div className="space-y-1">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="kind">Kind</Label>
            <select
              id="kind"
              className="w-full rounded-md border border-slate-300 p-2 text-sm"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label>Pipeline stages</Label>
            {STAGES.map((s) => (
              <label
                key={s.value}
                htmlFor={s.value}
                className="flex items-center gap-2 text-sm"
              >
                <Checkbox
                  id={s.value}
                  aria-label={s.label}
                  checked={stages.includes(s.value)}
                  onCheckedChange={() => toggleStage(s.value)}
                />
                {s.label}
              </label>
            ))}
          </div>
          <div className="space-y-1">
            <Label htmlFor="schema">Form schema (JSON)</Label>
            <Textarea
              id="schema"
              rows={5}
              className="font-mono text-xs"
              value={schemaText}
              onChange={(e) => setSchemaText(e.target.value)}
            />
            {errors.schema && (
              <p className="text-xs text-red-600">{errors.schema}</p>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default PostingForm;
