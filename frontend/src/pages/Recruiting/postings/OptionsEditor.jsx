import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import FieldError from "@/components/common/FieldError";
import { errorBorder } from "@/components/common/fieldErrors";
import { optionKey } from "@/pages/Recruiting/postings/postingValidation";

/** How a question reads in the reveal chips and picker (labels can be blank). */
const questionLabel = (q) => q.label || q.id;

/** One question an option reveals, with a button to stop revealing it. */
const RevealChip = ({ label, onRemove }) => (
  <span className="flex items-center gap-1 rounded-full border border-slate-300 px-2 py-0.5">
    {label}
    <button
      type="button"
      aria-label={`Stop revealing ${label}`}
      className="text-slate-500"
      onClick={onRemove}
    >
      ×
    </button>
  </span>
);

/**
 * Add/edit/remove the options of a choice question, and per option, pick which
 * of the form's other questions that option reveals.
 *
 * The reveal rule lives on the question being revealed (`showWhen`), so every
 * mutation here is a whole-form operation (`ops`) rather than a new options
 * array: renaming or removing an option has to rewrite other questions in the
 * same edit, which a component holding one question cannot do.
 *
 * @param {{questionId: string, options: string[],
 *          errors?: Record<string, string>,
 *          revealedBy: (option: string) => object[],
 *          pickable: (option: string) => object[],
 *          ops: {add: () => void, rename: (index: number, value: string) => void,
 *                remove: (index: number) => void,
 *                reveal: (option: string, questionId: string) => void,
 *                hide: (questionId: string) => void}}} props
 */
const OptionsEditor = ({
  questionId,
  options = [],
  errors = {},
  revealedBy,
  pickable,
  ops,
}) => (
  <div className="space-y-2">
    {options.map((opt, i) => {
      const revealed = revealedBy(opt);
      const candidates = pickable(opt);
      const errorKey = optionKey(questionId, i);
      return (
        <div
          key={i}
          className="space-y-2 rounded-md border border-slate-200 p-2"
        >
          <div className="flex items-center gap-2">
            <Input
              aria-label={`Option ${i + 1}`}
              className={errorBorder(errors, errorKey).trim()}
              value={opt}
              onChange={(e) => ops.rename(i, e.target.value)}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-label="Remove option"
              // Removing it would leave the questions it reveals waiting on
              // an answer no one can give.
              disabled={revealed.length > 0}
              onClick={() => ops.remove(i)}
            >
              Remove
            </Button>
          </div>
          <FieldError errors={errors} errorKey={errorKey} />
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
            Reveals
            {revealed.map((q) => (
              <RevealChip
                key={q.id}
                label={questionLabel(q)}
                onRemove={() => ops.hide(q.id)}
              />
            ))}
            {/* An option with no text yet can never be answered, so there is
                nothing to hang a question on. */}
            {opt.trim() !== "" && candidates.length > 0 && (
              <Select
                value={undefined}
                onValueChange={(id) => ops.reveal(opt, id)}
              >
                <SelectTrigger
                  aria-label={`Reveal a question when option ${i + 1} is selected`}
                  className="h-7 w-48"
                >
                  <SelectValue placeholder="+ Add question" />
                </SelectTrigger>
                <SelectContent>
                  {candidates.map((q) => (
                    <SelectItem key={q.id} value={q.id}>
                      {questionLabel(q)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
          {revealed.length > 0 && (
            <p className="text-xs text-slate-500">
              Stop revealing these to remove this option.
            </p>
          )}
        </div>
      );
    })}
    <Button type="button" variant="outline" size="sm" onClick={ops.add}>
      Add option
    </Button>
  </div>
);

export default OptionsEditor;
