import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { nextFieldKey, serialiseFields, parseSchema } from "./formBuilderUtils";

/**
 * The four supported field types and their display labels.
 *
 * @type {Array<{value: string, label: string}>}
 */
const FIELD_TYPES = [
  { value: "shortText", label: "Short text" },
  { value: "longText", label: "Long text" },
  { value: "singleChoice", label: "Single choice" },
  { value: "multiChoice", label: "Multi choice" },
];

/**
 * Controlled editor that lets an admin build the application-form JSON Schema
 * consumed by `JsonSchemaForm`. Maintains an ordered list of field descriptors
 * and serialises to `{ type:"object", properties, required }` on every change,
 * notifying the caller via `onChange`.
 *
 * @component
 * @param {Object}             props
 * @param {Object|undefined}   props.schema   - Initial JSON Schema; parsed on mount.
 * @param {Function}           props.onChange - Called with the updated schema on every change.
 */
const FormBuilder = ({ schema, onChange }) => {
  const [fields, setFields] = useState(() => parseSchema(schema));
  const [pendingType, setPendingType] = useState("shortText");

  /**
   * Applies a field update, persists it in state, and notifies the parent.
   *
   * @param {Array<{key:string, type:string, title:string, options:string[], required:boolean}>} next
   */
  const commit = (next) => {
    setFields(next);
    onChange(serialiseFields(next));
  };

  /** Appends a new blank field of the selected type. */
  const handleAdd = () => {
    const key = nextFieldKey(fields);
    const next = [
      ...fields,
      {
        key,
        type: pendingType,
        title: "",
        description: "",
        options: [],
        required: false,
      },
    ];
    commit(next);
  };

  /**
   * Updates a single field by index using a partial patch object.
   *
   * @param {number} index
   * @param {Partial<{key:string, type:string, title:string, description:string, options:string[], required:boolean}>} patch
   */
  const updateField = (index, patch) => {
    const next = fields.map((f, i) => (i === index ? { ...f, ...patch } : f));
    commit(next);
  };

  /**
   * Moves the field at `index` one position upward (swaps with previous).
   *
   * @param {number} index
   */
  const moveUp = (index) => {
    if (index === 0) return;
    const next = [...fields];
    [next[index - 1], next[index]] = [next[index], next[index - 1]];
    commit(next);
  };

  /**
   * Moves the field at `index` one position downward (swaps with next).
   *
   * @param {number} index
   */
  const moveDown = (index) => {
    if (index === fields.length - 1) return;
    const next = [...fields];
    [next[index], next[index + 1]] = [next[index + 1], next[index]];
    commit(next);
  };

  /**
   * Removes the field at `index`.
   *
   * @param {number} index
   */
  const deleteField = (index) => {
    commit(fields.filter((_, i) => i !== index));
  };

  const needsOptions = (type) =>
    type === "singleChoice" || type === "multiChoice";

  return (
    <div className="space-y-6">
      {/* Add-field toolbar */}
      <div className="flex items-center gap-2">
        <Select value={pendingType} onValueChange={setPendingType}>
          <SelectTrigger className="w-44" aria-label="Field type">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {FIELD_TYPES.map(({ value, label }) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button type="button" variant="outline" onClick={handleAdd}>
          Add field
        </Button>
      </div>

      {/* Field list */}
      {fields.length === 0 && (
        <p className="text-muted-foreground text-sm">
          No fields yet. Add one above.
        </p>
      )}

      <div className="space-y-4">
        {fields.map((field, index) => (
          <div key={field.key} className="rounded-lg border p-4 space-y-3">
            {/* Header row: type badge + reorder + delete */}
            <div className="flex items-center gap-2 justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {FIELD_TYPES.find((t) => t.value === field.type)?.label}
              </span>

              <div className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => moveUp(index)}
                  disabled={index === 0}
                  aria-label="Move up"
                >
                  ↑
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => moveDown(index)}
                  disabled={index === fields.length - 1}
                  aria-label="Move down"
                >
                  ↓
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => deleteField(index)}
                  aria-label="Delete"
                >
                  ✕
                </Button>
              </div>
            </div>

            {/* Title input */}
            <div className="space-y-1">
              <Label htmlFor={`${field.key}-title`}>Title</Label>
              <Input
                id={`${field.key}-title`}
                placeholder="Field title"
                value={field.title}
                onChange={(e) => updateField(index, { title: e.target.value })}
              />
            </div>

            {/* Description input (optional) */}
            <div className="space-y-1">
              <Label htmlFor={`${field.key}-description`}>
                Description{" "}
                <span className="text-muted-foreground font-normal">
                  (optional)
                </span>
              </Label>
              <Input
                id={`${field.key}-description`}
                placeholder="Helper text shown under the question"
                value={field.description}
                onChange={(e) =>
                  updateField(index, { description: e.target.value })
                }
              />
            </div>

            {/* Options input (singleChoice / multiChoice only) */}
            {needsOptions(field.type) && (
              <div className="space-y-1">
                <Label htmlFor={`${field.key}-options`}>
                  Options{" "}
                  <span className="text-muted-foreground font-normal">
                    (comma-separated)
                  </span>
                </Label>
                <Input
                  id={`${field.key}-options`}
                  placeholder="Option A, Option B"
                  value={field.options.join(", ")}
                  onChange={(e) =>
                    updateField(index, {
                      options: e.target.value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                />
              </div>
            )}

            {/* Required toggle */}
            <div className="flex items-center gap-2">
              <Checkbox
                id={`${field.key}-required`}
                checked={field.required}
                onCheckedChange={(checked) =>
                  updateField(index, { required: !!checked })
                }
              />
              <Label htmlFor={`${field.key}-required`}>Required</Label>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default FormBuilder;
