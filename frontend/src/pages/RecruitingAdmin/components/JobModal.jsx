import { useState, useEffect } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import FormBuilder from "@/components/recruiting/FormBuilder";

/** Empty JSON Schema used as the default form schema for a new posting. */
const EMPTY_SCHEMA = { type: "object", properties: {}, required: [] };

/** Empty form state for a new posting. */
const EMPTY_JOB_FORM = {
  title: "",
  description: "",
  mentorshipRole: "mentor",
  formSchema: EMPTY_SCHEMA,
};

/**
 * Maps a persisted job object back to the modal's flat form state.
 *
 * @param {Object} job - Existing job posting from the API.
 * @returns {{ title: string, description: string, mentorshipRole: string, formSchema: Object }}
 */
function jobToForm(job) {
  return {
    title: job.title ?? "",
    description: job.description ?? "",
    mentorshipRole: job.mentorshipRole ?? "mentor",
    formSchema: job.formSchema ?? EMPTY_SCHEMA,
  };
}

/**
 * Modal for creating or editing a job posting.
 *
 * Embeds {@link FormBuilder} to let admins construct the application-form JSON
 * Schema. The `kind` field is fixed to `"activity"` (no picker rendered).
 *
 * - Create mode: `open === true`, `job === null`
 * - Edit mode:   `open === true`, `job !== null`
 *
 * @component
 * @param {Object}          props
 * @param {boolean}         props.open       - Whether the dialog is visible.
 * @param {Object|null}     props.job        - Posting being edited, or null for create.
 * @param {() => void}      props.onClose    - Callback to close without saving.
 * @param {(payload: Object) => Promise<void>} props.onSave - Callback invoked with the form payload on submit.
 * @param {boolean}         [props.readOnly] - When true, all controls are disabled.
 */
export default function JobModal({
  open,
  job,
  onClose,
  onSave,
  readOnly = false,
}) {
  const isEdit = job != null;

  const [form, setForm] = useState(EMPTY_JOB_FORM);
  const [apiError, setApiError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  // Re-initialise form whenever the modal opens or the target job changes.
  useEffect(() => {
    if (!open) return;
    setForm(isEdit ? jobToForm(job) : { ...EMPTY_JOB_FORM });
    setApiError(null);
    setIsSaving(false);
  }, [open, job, isEdit]);

  /**
   * Returns a setter for a single top-level form key.
   *
   * @param {string} key
   * @returns {(value: unknown) => void}
   */
  const setField = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));

  /** Validates required fields and calls `onSave` with the assembled payload. */
  const submitForm = async () => {
    if (!form.title.trim()) return;

    setApiError(null);
    setIsSaving(true);
    try {
      await onSave({
        title: form.title.trim(),
        description: form.description.trim(),
        kind: "activity",
        mentorshipRole: form.mentorshipRole,
        formSchema: form.formSchema,
      });
    } catch (err) {
      const msg = err?.response?.data?.message || err?.message;
      setApiError(msg ?? "Failed to save posting. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
    >
      <DialogContent
        className="sm:max-w-2xl max-h-[90vh] flex flex-col z-[200]"
        onOpenAutoFocus={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle className="text-xl">
            {readOnly
              ? "View Posting"
              : isEdit
                ? "Edit Posting"
                : "Create Posting"}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-1">
          <div className="space-y-4 py-2">
            {/* Title */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="job-title">
                Title <span className="text-red-500">*</span>
              </Label>
              <Input
                id="job-title"
                placeholder="e.g. Software Engineer Mentor"
                value={form.title}
                onChange={(e) => setField("title")(e.target.value)}
                disabled={readOnly}
              />
            </div>

            {/* Description / JD */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="job-description">Job Description</Label>
              <textarea
                id="job-description"
                placeholder="Describe the role and expectations…"
                value={form.description}
                onChange={(e) => setField("description")(e.target.value)}
                disabled={readOnly}
                rows={4}
                className="w-full border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed resize-none"
              />
            </div>

            {/* Kind — fixed to activity, displayed for transparency */}
            <div className="flex flex-col gap-1.5">
              <Label>Kind</Label>
              <Input value="activity" disabled className="w-32" />
            </div>

            {/* Mentorship Role */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="job-mentorship-role">Mentorship Role</Label>
              <Select
                value={form.mentorshipRole}
                onValueChange={setField("mentorshipRole")}
                disabled={readOnly}
              >
                <SelectTrigger id="job-mentorship-role" className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="z-[201]">
                  <SelectItem value="mentor">Mentor</SelectItem>
                  <SelectItem value="mentee">Mentee</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Application Form Builder */}
            <div className="flex flex-col gap-2">
              <Label className="text-sm font-semibold">Application Form</Label>
              <p className="text-sm text-muted-foreground">
                Build the questions candidates will answer when applying.
              </p>
              <FormBuilder
                schema={form.formSchema}
                onChange={setField("formSchema")}
              />
            </div>

            {apiError && (
              <span className="text-destructive text-xs">{apiError}</span>
            )}
          </div>
          <div className="pointer-events-none sticky bottom-0 h-8 bg-gradient-to-t from-background to-transparent" />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            {readOnly ? "Close" : "Cancel"}
          </Button>
          {!readOnly && (
            <Button
              onClick={submitForm}
              disabled={isSaving || !form.title.trim()}
            >
              {isSaving ? "Saving…" : "Save"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
