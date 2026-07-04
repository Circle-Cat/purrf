import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { rubricFor } from "@/pages/Recruiting/applications/evaluationRubric";

/** The 1-5 score options rendered as a button group for `valueType: "score"` fields. */
const SCORE_OPTIONS = [1, 2, 3, 4, 5];

/**
 * One rubric field's input(s): a Pass/Fail toggle for `pass_fail`, a 1-5
 * button group for `score`, and/or a `Textarea` for free-text notes (either
 * the field IS notes, i.e. `valueType === "notes"`, or it pairs notes
 * alongside its main value via `hasNotes`). Mirrors `SubStatusSelector`'s
 * `Button` + `aria-pressed` toggle pattern from `ApplicationDetailPage.jsx`.
 *
 * @param {{field: {id: string, label: string, valueType: string,
 *          hasNotes?: boolean}, entry: {value?: boolean|number,
 *          notes?: string}|undefined, readOnly: boolean,
 *          onValueChange: (fieldId: string, value: boolean|number) => void,
 *          onNotesChange: (fieldId: string, notes: string) => void}} props
 */
const RubricFieldInput = ({
  field,
  entry,
  readOnly,
  onValueChange,
  onNotesChange,
}) => {
  const value = entry?.value;
  const notes = entry?.notes ?? "";
  const showNotes = field.valueType === "notes" || field.hasNotes;

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-700">{field.label}</p>
      {field.valueType === "pass_fail" && (
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant={value === true ? "default" : "outline"}
            aria-pressed={value === true}
            disabled={readOnly}
            onClick={() => onValueChange(field.id, true)}
          >
            Pass
          </Button>
          <Button
            type="button"
            size="sm"
            variant={value === false ? "default" : "outline"}
            aria-pressed={value === false}
            disabled={readOnly}
            onClick={() => onValueChange(field.id, false)}
          >
            Fail
          </Button>
        </div>
      )}
      {field.valueType === "score" && (
        <div className="flex flex-wrap gap-2">
          {SCORE_OPTIONS.map((option) => (
            <Button
              key={option}
              type="button"
              size="sm"
              variant={value === option ? "default" : "outline"}
              aria-pressed={value === option}
              disabled={readOnly}
              onClick={() => onValueChange(field.id, option)}
            >
              {option}
            </Button>
          ))}
        </div>
      )}
      {showNotes && (
        <Textarea
          placeholder="Notes"
          value={notes}
          disabled={readOnly}
          onChange={(e) => onNotesChange(field.id, e.target.value)}
        />
      )}
    </div>
  );
};

/**
 * Presentational interview-evaluation scorecard: renders the fixed rubric
 * for `stage` (via `rubricFor`), owns its own in-progress draft edits as
 * local state, and only calls out to the parent on explicit "Save draft" /
 * "Confirm & Submit" actions. Does not call any API itself — the parent
 * page owns the network calls.
 *
 * @param {{stage: string, initialResponses?: Object<string, {value?:
 *          boolean|number, notes?: string}>, readOnly?: boolean,
 *          saving?: boolean, onSaveDraft: (responses: object) => void,
 *          onConfirm: (responses: object) => void}} props
 */
const EvaluationRubricForm = ({
  stage,
  initialResponses,
  readOnly = false,
  saving = false,
  onSaveDraft,
  onConfirm,
}) => {
  const [responses, setResponses] = useState(initialResponses ?? {});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const sections = rubricFor(stage) ?? [];

  const handleValueChange = (fieldId, value) => {
    setResponses((prev) => ({
      ...prev,
      [fieldId]: { ...prev[fieldId], value },
    }));
  };

  const handleNotesChange = (fieldId, notes) => {
    setResponses((prev) => ({
      ...prev,
      [fieldId]: { ...prev[fieldId], notes },
    }));
  };

  return (
    <div className="space-y-6">
      {sections.map((section) => (
        <div key={section.title} className="space-y-4">
          <h3 className="text-sm font-semibold text-slate-800">
            {section.title}
          </h3>
          <div className="space-y-4">
            {section.fields.map((field) => (
              <RubricFieldInput
                key={field.id}
                field={field}
                entry={responses[field.id]}
                readOnly={readOnly}
                onValueChange={handleValueChange}
                onNotesChange={handleNotesChange}
              />
            ))}
          </div>
        </div>
      ))}
      {!readOnly && (
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={saving}
            onClick={() => onSaveDraft(responses)}
          >
            Save draft
          </Button>
          <Button
            type="button"
            disabled={saving}
            onClick={() => setConfirmOpen(true)}
          >
            Confirm & Submit
          </Button>
        </div>
      )}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm & Submit</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-600">
            This cannot be edited after submitting.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={saving}
              onClick={() => {
                setConfirmOpen(false);
                onConfirm(responses);
              }}
            >
              Submit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EvaluationRubricForm;
