import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * Add/edit/remove the options of a choice question.
 *
 * @param {{options: string[], onChange: (next: string[]) => void}} props
 */
const OptionsEditor = ({ options = [], onChange }) => {
  const editAt = (i, value) =>
    onChange(options.map((o, idx) => (idx === i ? value : o)));
  const removeAt = (i) => onChange(options.filter((_, idx) => idx !== i));
  const add = () => onChange([...options, ""]);

  return (
    <div className="space-y-2">
      {options.map((opt, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input
            aria-label={`Option ${i + 1}`}
            value={opt}
            onChange={(e) => editAt(i, e.target.value)}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-label="Remove option"
            onClick={() => removeAt(i)}
          >
            Remove
          </Button>
        </div>
      ))}
      <Button type="button" variant="outline" size="sm" onClick={add}>
        Add option
      </Button>
    </div>
  );
};

export default OptionsEditor;
