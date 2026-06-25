import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import FormBuilder from "./vendor/FormBuilder";
import ApplicationPreview from "./ApplicationPreview";
import { STAGES, PROFILE_FIELDS, REQ_LEVELS } from "./mockData";

/** Maps each template to an ordered list of stage keys (or a special string). */
const TEMPLATE_STAGES = {
  Intern: [
    "recruiter_screening",
    "behavioral",
    "tech",
    "board_review",
    "offer",
  ],
  Mentee: ["recruiter_screening"],
  Mentor: null, // auto-approve path
};

/**
 * Default requirement level per template. Each profile section is "off" (not
 * shown), "optional" (shown, can skip), or "required". Mirrors the real
 * Workable forms: Education/Experience/Summary optional, Resume required;
 * Mentor relaxes Resume to optional too.
 */
const TEMPLATE_DEFAULTS = {
  Intern: {
    education: "optional",
    experience: "optional",
    summary: "optional",
    resume: "required",
  },
  Mentee: {
    education: "optional",
    experience: "optional",
    summary: "optional",
    resume: "required",
  },
  Mentor: {
    education: "optional",
    experience: "optional",
    summary: "optional",
    resume: "optional",
  },
};

/**
 * Renders a pipeline preview line for the given template.
 *
 * @param {string} template - One of "Intern" | "Mentee" | "Mentor".
 * @returns {JSX.Element}
 */
function PipelinePreview({ template }) {
  const stageKeys = TEMPLATE_STAGES[template];

  if (template === "Mentor") {
    return (
      <p className="text-sm text-muted-foreground">
        Pipeline:{" "}
        <span className="font-medium text-foreground">
          Auto-approve (google.com email)
        </span>
      </p>
    );
  }

  if (!stageKeys || stageKeys.length === 0) {
    return <p className="text-sm text-muted-foreground">Pipeline: —</p>;
  }

  return (
    <p className="text-sm text-muted-foreground flex flex-wrap items-center gap-1">
      <span>Pipeline:</span>
      {stageKeys.map((key, i) => (
        <span key={key} className="flex items-center gap-1">
          <Badge variant="secondary" className="font-normal">
            {STAGES[key]?.label ?? key}
          </Badge>
          {i < stageKeys.length - 1 && (
            <span className="text-muted-foreground">→</span>
          )}
        </span>
      ))}
    </p>
  );
}

/** All stage keys in canonical pipeline order (for the Custom composer). */
const ALL_STAGE_KEYS = Object.keys(STAGES);

/**
 * Editable stage picker shown for the "Custom" template: the admin chooses
 * which stages the pipeline includes; the result is always kept in canonical
 * order regardless of click order.
 *
 * @param {Object} props
 * @param {string[]} props.value - Selected stage keys.
 * @param {(next: string[]) => void} props.onChange - Receives the reordered selection.
 * @returns {JSX.Element}
 */
function CustomPipelineEditor({ value, onChange }) {
  const toggle = (key, checked) => {
    const next = checked
      ? ALL_STAGE_KEYS.filter((k) => value.includes(k) || k === key)
      : value.filter((k) => k !== key);
    onChange(next);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {ALL_STAGE_KEYS.map((key) => (
          <div key={key} className="flex items-center gap-2">
            <Checkbox
              id={`stage-${key}`}
              checked={value.includes(key)}
              onCheckedChange={(checked) => toggle(key, !!checked)}
            />
            <Label
              htmlFor={`stage-${key}`}
              className="font-normal cursor-pointer"
            >
              {STAGES[key].label}
            </Label>
          </div>
        ))}
      </div>
      <p className="text-sm text-muted-foreground flex flex-wrap items-center gap-1">
        <span>Pipeline:</span>
        {value.length === 0 ? (
          <span className="italic">— pick at least one stage</span>
        ) : (
          value.map((key, i) => (
            <span key={key} className="flex items-center gap-1">
              <Badge variant="secondary" className="font-normal">
                {STAGES[key].label}
              </Badge>
              {i < value.length - 1 && (
                <span className="text-muted-foreground">→</span>
              )}
            </span>
          ))
        )}
      </p>
    </div>
  );
}

/** Derive the job kind from its template (only Intern is employment). */
const kindForTemplate = (template) =>
  template === "Intern" ? "employment" : "activity";

/**
 * "Create / Edit Posting" inline card for the Recruiting v2 prototype.
 *
 * Lets stakeholders see the full posting-creation flow — title, description,
 * template picker with derived pipeline preview, profile-requirement toggles,
 * and a tabbed application-form builder — with no backend dependency. Reused
 * for both create (initialJob = null) and edit (initialJob = the posting).
 *
 * @component
 * @param {Object} props
 * @param {object|null} [props.initialJob] - Posting to prefill when editing; null = create.
 * @param {(job: object) => void} [props.onSave] - Receives the assembled job-like
 *   object ({title, kind, template, stages, description}). Falls back to a console
 *   log if omitted (standalone demo).
 * @param {() => void} [props.onClose] - Called after save / on cancel; shows a Cancel button.
 * @returns {JSX.Element}
 */
const JobModalPrototype = ({ initialJob = null, onSave, onClose }) => {
  const [title, setTitle] = useState(initialJob?.title ?? "");
  const [description, setDescription] = useState(initialJob?.description ?? "");
  const [template, setTemplate] = useState(initialJob?.template ?? "Intern");
  const [customStages, setCustomStages] = useState(
    initialJob?.template === "Custom" && initialJob?.stages?.length
      ? initialJob.stages
      : ["recruiter_screening"],
  );

  const [profileReq, setProfileReq] = useState(
    TEMPLATE_DEFAULTS[initialJob?.template] ?? TEMPLATE_DEFAULTS.Intern,
  );

  /** Returns a setter that updates one profile section's requirement level. */
  const setFieldLevel = (key) => (level) =>
    setProfileReq((prev) => ({ ...prev, [key]: level }));

  const [formSchema, setFormSchema] = useState({
    type: "object",
    properties: {},
    required: [],
  });
  const [showPreview, setShowPreview] = useState(false);

  /** When the template changes, update derived profile-requirement defaults. */
  const handleTemplateChange = (next) => {
    setTemplate(next);
    const defaults = TEMPLATE_DEFAULTS[next];
    if (defaults) setProfileReq(defaults);
  };

  /**
   * Assemble the posting and hand it to onSave (or log it when standalone),
   * then close. Stages come from the Custom composer or the template preset;
   * Mentor's null preset collapses to an empty pipeline.
   */
  const handleSave = () => {
    const stages =
      template === "Custom" ? customStages : (TEMPLATE_STAGES[template] ?? []);
    const job = {
      title,
      kind: kindForTemplate(template),
      template,
      stages,
      description,
    };
    if (onSave) onSave(job);
    else console.log("[prototype] save posting", { ...job, profileReq, formSchema });
    onClose?.();
  };

  return (
    <Card className="max-w-2xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold">
          {initialJob ? "Edit Posting" : "Create Posting"}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Define the role, pipeline, and application form for this posting.
        </p>
      </div>

      <Separator />

      {/* Title */}
      <div className="space-y-1.5">
        <Label htmlFor="posting-title">Title</Label>
        <Input
          id="posting-title"
          placeholder="e.g. Software Engineer Intern — Summer 2027"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </div>

      {/* Job Description */}
      <div className="space-y-1.5">
        <Label htmlFor="posting-description">Job Description</Label>
        <textarea
          id="posting-description"
          rows={4}
          placeholder="Describe the role, responsibilities, and expected commitment…"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
        />
      </div>

      {/* Template Picker */}
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="posting-template">Template</Label>
          <p className="text-xs text-muted-foreground">
            The template sets the role type and pipeline — no separate role
            dropdown needed. Pick Custom to compose the pipeline yourself.
          </p>
          <Select value={template} onValueChange={handleTemplateChange}>
            <SelectTrigger id="posting-template" className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Mentor">Mentor</SelectItem>
              <SelectItem value="Mentee">Mentee</SelectItem>
              <SelectItem value="Intern">Intern</SelectItem>
              <SelectItem value="Custom">Custom</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Pipeline: read-only preview for presets, editable composer for Custom */}
        {template === "Custom" ? (
          <CustomPipelineEditor
            value={customStages}
            onChange={setCustomStages}
          />
        ) : (
          <PipelinePreview template={template} />
        )}
      </div>

      <Separator />

      {/* Profile Requirements */}
      <div className="space-y-3">
        <div>
          <p className="text-sm font-medium">Profile requirements</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            For each profile section, choose whether it is hidden, optional, or
            required on this posting&apos;s application.
          </p>
        </div>
        <div className="space-y-2">
          {PROFILE_FIELDS.map((f) => (
            <div
              key={f.key}
              className="flex items-center justify-between rounded-lg border px-3 py-2"
            >
              <span className="text-sm">{f.label}</span>
              <Select
                value={profileReq[f.key]}
                onValueChange={setFieldLevel(f.key)}
              >
                <SelectTrigger className="w-40 capitalize">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REQ_LEVELS.map((lvl) => (
                    <SelectItem key={lvl} value={lvl} className="capitalize">
                      {lvl === "off" ? "Not included" : lvl}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ))}
        </div>
      </div>

      <Separator />

      {/* Application Form */}
      <div className="space-y-3">
        <div>
          <p className="text-sm font-medium">Application Form</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Build the custom questions applicants will answer when they apply.
          </p>
        </div>

        <FormBuilder schema={formSchema} onChange={setFormSchema} />
      </div>

      <Separator />

      {/* Actions — Preview is a peer of Save: it reviews the whole posting */}
      <div className="flex justify-end gap-2">
        {onClose && (
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        )}
        <Button variant="outline" onClick={() => setShowPreview(true)}>
          Preview
        </Button>
        <Button onClick={handleSave}>Save posting</Button>
      </div>

      {/* Whole-posting preview (candidate's view) */}
      <Dialog open={showPreview} onOpenChange={setShowPreview}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Application preview</DialogTitle>
          </DialogHeader>
          <ApplicationPreview
            title={title}
            profileReq={profileReq}
            schema={formSchema}
          />
        </DialogContent>
      </Dialog>
    </Card>
  );
};

export default JobModalPrototype;
