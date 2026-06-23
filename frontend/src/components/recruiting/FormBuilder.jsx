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
 * Derives a unique field key such as `field_1`, `field_2`, … by scanning the
 * existing fields for the highest numeric suffix and incrementing it.
 *
 * @param {Array<{key: string}>} fields - The current ordered field list.
 * @returns {string} A unique key not already present in `fields`.
 */
export function nextFieldKey(fields) {
  let max = 0;
  for (const f of fields) {
    const m = /^field_(\d+)$/.exec(f.key);
    if (m) {
      const n = parseInt(m[1], 10);
      if (n > max) max = n;
    }
  }
  return `field_${max + 1}`;
}

/**
 * Serialises an ordered array of field descriptors into a JSON Schema object
 * shaped as `{ type:"object", properties, required }`. The mapping is:
 *
 * - `shortText`    → `{ type:"string", title }`
 * - `longText`     → `{ type:"string", title, "x-widget":"textarea" }`
 * - `singleChoice` → `{ type:"string", title, enum: options }`
 * - `multiChoice`  → `{ type:"array",  title, items:{ enum: options } }`
 *
 * Property insertion order mirrors the field array order so that consumers
 * can rely on `Object.entries(properties)` for rendering.
 *
 * @param {Array<{key:string, type:string, title:string, options:string[], required:boolean}>} fields
 * @returns {{ type: "object", properties: Object, required: string[] }} JSON Schema fragment.
 */
export function serialiseFields(fields) {
  const properties = {};
  const required = [];

  for (const field of fields) {
    let fragment;
    switch (field.type) {
      case "longText":
        fragment = { type: "string", title: field.title, "x-widget": "textarea" };
        break;
      case "singleChoice":
        fragment = { type: "string", title: field.title, enum: field.options };
        break;
      case "multiChoice":
        fragment = { type: "array", title: field.title, items: { enum: field.options } };
        break;
      case "shortText":
      default:
        fragment = { type: "string", title: field.title };
        break;
    }
    properties[field.key] = fragment;
    if (field.required) {
      required.push(field.key);
    }
  }

  return { type: "object", properties, required };
}

/**
 * Parses a JSON Schema object produced by {@link serialiseFields} back into the
 * ordered mutable field array used by `FormBuilder`'s internal state.
 *
 * @param {Object|undefined} schema - JSON Schema to parse; treated as empty when falsy.
 * @returns {Array<{key:string, type:string, title:string, options:string[], required:boolean}>}
 */
export function parseSchema(schema) {
  if (!schema?.properties) return [];
  const requiredSet = new Set(schema.required ?? []);
  return Object.entries(schema.properties).map(([key, field]) => {
    let type = "shortText";
    let options = [];

    if (field.type === "array" && field.items?.enum) {
      type = "multiChoice";
      options = field.items.enum;
    } else if (field.type === "string" && field["x-widget"] === "textarea") {
      type = "longText";
    } else if (field.type === "string" && field.enum) {
      type = "singleChoice";
      options = field.enum;
    }

    return {
      key,
      type,
      title: field.title ?? "",
      options,
      required: requiredSet.has(key),
    };
  });
}

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
      { key, type: pendingType, title: "", options: [], required: false },
    ];
    commit(next);
  };

  /**
   * Updates a single field by index using a partial patch object.
   *
   * @param {number} index
   * @param {Partial<{key:string, type:string, title:string, options:string[], required:boolean}>} patch
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
          <div
            key={field.key}
            className="rounded-lg border p-4 space-y-3"
          >
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
