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
 * @param {Array<{key:string, type:string, title:string, options:string[], required:boolean, description:string}>} fields
 * @returns {{ type: "object", properties: Object, required: string[] }} JSON Schema fragment.
 */
export function serialiseFields(fields) {
  const properties = {};
  const required = [];

  for (const field of fields) {
    let fragment;
    switch (field.type) {
      case "longText":
        fragment = {
          type: "string",
          title: field.title,
          "x-widget": "textarea",
        };
        break;
      case "singleChoice":
        fragment = { type: "string", title: field.title, enum: field.options };
        break;
      case "multiChoice":
        fragment = {
          type: "array",
          title: field.title,
          items: { enum: field.options },
        };
        break;
      case "shortText":
      default:
        fragment = { type: "string", title: field.title };
        break;
    }
    properties[field.key] = fragment;
    if (field.description) {
      fragment.description = field.description;
    }
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
 * @returns {Array<{key:string, type:string, title:string, options:string[], required:boolean, description:string}>}
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
      description: field.description ?? "",
      options,
      required: requiredSet.has(key),
    };
  });
}
