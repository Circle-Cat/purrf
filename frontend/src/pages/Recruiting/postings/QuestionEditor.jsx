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

const CHOICE_TYPES = new Set(["single_choice", "multi_choice"]);
const NONE = "__none__";

/**
 * Editor for a single submission-form question: label, required flag,
 * type-specific fields, and a single-layer showWhen rule.
 *
 * @param {{question: object, allQuestions: object[],
 *          onChange: (q: object) => void, onRemove: () => void,
 *          onMoveUp: () => void, onMoveDown: () => void}} props
 */
const QuestionEditor = ({
  question,
  allQuestions,
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
}) => {
  const patch = (fields) => onChange({ ...question, ...fields });
  const others = allQuestions.filter((q) => q.id !== question.id);
  const depId = question.showWhen?.questionId ?? "";

  const setDep = (questionId) =>
    patch({
      showWhen: questionId
        ? { questionId, equals: question.showWhen?.equals ?? "" }
        : undefined,
    });
  const setEquals = (equals) =>
    patch({ showWhen: { questionId: depId, equals } });

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

      <div className="space-y-1">
        <Label htmlFor={`${question.id}-label`}>Label</Label>
        <Input
          id={`${question.id}-label`}
          aria-label="Label"
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
          onChange={(options) =>
            patch({
              options,
              ...(question.otherOption &&
              !options.includes(question.otherOption)
                ? { otherOption: undefined }
                : {}),
            })
          }
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

      <div className="flex gap-3">
        <div className="space-y-1">
          <Label htmlFor={`${question.id}-dep`}>Depends on</Label>
          <Select
            value={depId || NONE}
            onValueChange={(v) => setDep(v === NONE ? "" : v)}
          >
            <SelectTrigger
              id={`${question.id}-dep`}
              aria-label="Depends on"
              className="max-w-xs"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>— none —</SelectItem>
              {others.map((q) => (
                <SelectItem key={q.id} value={q.id}>
                  {q.label || q.id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {depId && (
          <div className="space-y-1">
            <Label htmlFor={`${question.id}-eq`}>Equals</Label>
            <Input
              id={`${question.id}-eq`}
              aria-label="Equals"
              value={question.showWhen?.equals ?? ""}
              onChange={(e) => setEquals(e.target.value)}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default QuestionEditor;
