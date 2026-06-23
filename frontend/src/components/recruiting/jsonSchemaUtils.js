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
