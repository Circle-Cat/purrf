import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import OptionsEditor from "@/pages/Recruiting/postings/OptionsEditor";
import { revealedBy as revealedByOption } from "@/pages/Recruiting/postings/questionTypes";

const CHOICE_TYPES = new Set(["single_choice", "multi_choice"]);
const NONE = "__none__";

/**
 * Editor for a single submission-form question: label, required flag,
 * type-specific fields, and -- for choice types -- which questions each of
 * its options reveals.
 *
 * A question's own reveal condition is NOT editable here. It is authored from
 * the choice question that reveals it (see `OptionsEditor`), and shown here
 * read-only so a question that never appears on its own is still explicable.
 *
 * `optionOps` carries the whole-form operations `OptionsEditor` needs; see its
 * JSDoc for why option edits cannot be expressed as a new options array.
 *
 * @param {{question: object, allQuestions: object[],
 *          onChange: (q: object) => void, onRemove: () => void,
 *          onMoveUp: () => void, onMoveDown: () => void,
 *          optionOps: object}} props
 */
const QuestionEditor = ({
  question,
  allQuestions,
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
  optionOps,
}) => {
  const patch = (fields) => onChange({ ...question, ...fields });

  /** The questions this question's option `opt` reveals. */
  const revealedBy = (opt) => revealedByOption(allQuestions, question.id, opt);
  /**
   * What `opt` can still be pointed at: any other question it isn't already
   * revealing. The question this one is revealed by is excluded too -- a pair
   * that reveals each other can never be answered, so neither would appear.
   */
  const pickable = (opt) => {
    const already = new Set(revealedBy(opt).map((q) => q.id));
    return allQuestions.filter(
      (q) =>
        q.id !== question.id &&
        q.id !== question.showWhen?.questionId &&
        !already.has(q.id),
    );
  };

  /**
   * How to name the question that reveals this one. Falls back for a dangling
   * rule: deleting a question leaves the ones it revealed pointing at an id
   * that is gone, and saying so beats naming nothing.
   */
  const parentLabel = () => {
    const parent = allQuestions.find(
      (q) => q.id === question.showWhen.questionId,
    );
    return parent ? `"${parent.label || parent.id}"` : "a removed question";
  };

  return (
    <div className="space-y-3 rounded-md border border-slate-200 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase text-slate-500">
          {question.type}
        </span>
        <div className="flex gap-1">
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-label="Move up"
            onClick={onMoveUp}
          >
            ↑
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-label="Move down"
            onClick={onMoveDown}
          >
            ↓
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-label="Remove question"
            onClick={onRemove}
          >
            Remove
          </Button>
        </div>
      </div>

      {question.showWhen && (
        <p className="text-xs text-slate-500">
          Only shown when {parentLabel()} = &quot;
          {question.showWhen.equals}&quot;
        </p>
      )}

      <div className="space-y-1">
        {/* The schema field is `label`, but to an author this row is the
            question they are asking, so the form says so. */}
        <Label htmlFor={`${question.id}-label`}>Question</Label>
        <Input
          id={`${question.id}-label`}
          aria-label="Question"
          value={question.label}
          onChange={(e) => patch({ label: e.target.value })}
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor={`${question.id}-description`}>
          Description (optional)
        </Label>
        <Textarea
          id={`${question.id}-description`}
          aria-label="Description"
          rows={2}
          value={question.description ?? ""}
          onChange={(e) => patch({ description: e.target.value || undefined })}
        />
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          id={`${question.id}-required`}
          checked={question.required}
          onCheckedChange={(v) => patch({ required: !!v })}
        />
        <Label htmlFor={`${question.id}-required`}>Required</Label>
      </div>

      {CHOICE_TYPES.has(question.type) && (
        <OptionsEditor
          options={question.options ?? []}
          revealedBy={revealedBy}
          pickable={pickable}
          ops={optionOps}
        />
      )}
      {CHOICE_TYPES.has(question.type) && (
        <div className="space-y-1">
          <Label htmlFor={`${question.id}-other`}>
            Reveal a text box when this option is selected
          </Label>
          <Select
            value={question.otherOption ?? NONE}
            onValueChange={(v) =>
              patch({ otherOption: v === NONE ? undefined : v })
            }
          >
            <SelectTrigger
              id={`${question.id}-other`}
              aria-label="Other option"
              className="max-w-xs"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>— none —</SelectItem>
              {(question.options ?? [])
                .filter((o) => o && o.trim() !== "")
                .map((o) => (
                  <SelectItem key={o} value={o}>
                    {o}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
      )}
      {question.type === "multi_choice" && (
        <div className="space-y-1">
          <Label htmlFor={`${question.id}-maxsel`}>Max selections</Label>
          <Input
            id={`${question.id}-maxsel`}
            aria-label="Max selections"
            type="number"
            value={question.maxSelections ?? ""}
            onChange={(e) =>
              patch({
                maxSelections: e.target.value
                  ? Number(e.target.value)
                  : undefined,
              })
            }
          />
        </div>
      )}
      {question.type === "long_text" && (
        <div className="flex gap-3">
          <div className="space-y-1">
            <Label htmlFor={`${question.id}-maxlen`}>Max length</Label>
            <Input
              id={`${question.id}-maxlen`}
              aria-label="Max length"
              type="number"
              value={question.maxLength ?? ""}
              onChange={(e) =>
                patch({
                  maxLength: e.target.value
                    ? Number(e.target.value)
                    : undefined,
                })
              }
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`${question.id}-maxwords`}>Max words</Label>
            <Input
              id={`${question.id}-maxwords`}
              aria-label="Max words"
              type="number"
              value={question.maxWords ?? ""}
              onChange={(e) =>
                patch({
                  maxWords: e.target.value ? Number(e.target.value) : undefined,
                })
              }
            />
          </div>
        </div>
      )}
      {question.type === "exact_text" && (
        <div className="space-y-1">
          <Label htmlFor={`${question.id}-expected`}>Expected value</Label>
          <Input
            id={`${question.id}-expected`}
            aria-label="Expected value"
            value={question.expectedValue ?? ""}
            onChange={(e) => patch({ expectedValue: e.target.value })}
          />
        </div>
      )}
    </div>
  );
};

export default QuestionEditor;
