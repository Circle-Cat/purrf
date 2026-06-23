import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";

/**
 * Validates an answers object against a JSON Schema's `required` array.
 * Returns an error map `{ [key]: "Required" }` for each required field that
 * is missing or empty; returns `{}` when all required fields are present.
 *
 * @param {Object} schema - JSON Schema object with optional `required` array.
 * @param {Object} value  - The current answers keyed by property name.
 * @returns {{ [key: string]: string }} Error map (empty when valid).
 */
export function validate(schema, value) {
  const errors = {};
  const required = schema.required ?? [];
  for (const key of required) {
    const v = value[key];
    const empty =
      v === undefined ||
      v === null ||
      v === "" ||
      (Array.isArray(v) && v.length === 0);
    if (empty) {
      errors[key] = "Required";
    }
  }
  return errors;
}

/**
 * Controlled form renderer for a JSON Schema `object`. Supports four field
 * types drawn from `schema.properties`:
 *
 * - `{ type: "string", title }` → shadcn `Input`
 * - `{ type: "string", title, "x-widget": "textarea" }` → Tailwind `<textarea>`
 * - `{ type: "string", title, enum: [...] }` → shadcn `RadioGroup`
 * - `{ type: "array", title, items: { enum: [...] } }` → group of shadcn `Checkbox`
 *
 * Every field has an `id` matching the property key so that
 * `screen.getByLabelText(title)` resolves in tests.
 *
 * @component
 * @param {Object}   props
 * @param {Object}   props.schema   - JSON Schema object describing the fields.
 * @param {Object}   props.value    - Current answers keyed by property name.
 * @param {Function} props.onChange - Called with the merged answers object on edit.
 */
const JsonSchemaForm = ({ schema, value, onChange }) => {
  const properties = schema.properties ?? {};

  /** Merge a single field update into the current answers object. */
  const handleChange = (key, next) => {
    onChange({ ...value, [key]: next });
  };

  return (
    <div className="space-y-6">
      {Object.entries(properties).map(([key, field]) => {
        const title = field.title ?? key;

        // Multi-choice: array type with items.enum
        if (field.type === "array" && field.items?.enum) {
          const options = field.items.enum;
          const selected = Array.isArray(value[key]) ? value[key] : [];

          return (
            <fieldset key={key} className="space-y-2">
              <legend className="text-sm font-medium leading-none select-none">
                {title}
              </legend>
              <div className="space-y-1">
                {options.map((option) => {
                  const optionId = `${key}-${option}`;
                  const checked = selected.includes(option);
                  return (
                    <div key={option} className="flex items-center gap-2">
                      <Checkbox
                        id={optionId}
                        checked={checked}
                        onCheckedChange={(isChecked) => {
                          const next = isChecked
                            ? [...selected, option]
                            : selected.filter((v) => v !== option);
                          handleChange(key, next);
                        }}
                      />
                      <Label htmlFor={optionId}>{option}</Label>
                    </div>
                  );
                })}
              </div>
            </fieldset>
          );
        }

        // Single-choice: string type with enum
        if (field.type === "string" && field.enum) {
          const options = field.enum;
          return (
            <div key={key} className="space-y-2">
              <Label htmlFor={key}>{title}</Label>
              <RadioGroup
                id={key}
                value={value[key] ?? ""}
                onValueChange={(next) => handleChange(key, next)}
                className="space-y-1"
              >
                {options.map((option) => {
                  const optionId = `${key}-${option}`;
                  return (
                    <div key={option} className="flex items-center gap-2">
                      <RadioGroupItem id={optionId} value={option} />
                      <Label htmlFor={optionId}>{option}</Label>
                    </div>
                  );
                })}
              </RadioGroup>
            </div>
          );
        }

        // Long text: string with x-widget=textarea
        if (field.type === "string" && field["x-widget"] === "textarea") {
          return (
            <div key={key} className="space-y-2">
              <Label htmlFor={key}>{title}</Label>
              <textarea
                id={key}
                value={value[key] ?? ""}
                onChange={(e) => handleChange(key, e.target.value)}
                className="border-input placeholder:text-muted-foreground dark:bg-input/30 focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3 flex min-h-24 w-full rounded-lg border bg-transparent px-3 py-2 text-sm transition-colors outline-none resize-y disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>
          );
        }

        // Short text: string (default)
        return (
          <div key={key} className="space-y-2">
            <Label htmlFor={key}>{title}</Label>
            <Input
              id={key}
              value={value[key] ?? ""}
              onChange={(e) => handleChange(key, e.target.value)}
            />
          </div>
        );
      })}
    </div>
  );
};

export default JsonSchemaForm;
