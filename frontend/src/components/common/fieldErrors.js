/**
 * Class to append to a control that failed validation.
 *
 * Separate from `FieldError` because a module exporting a component may not
 * export anything else (react-refresh/only-export-components), and separate
 * from either validation module because both the posting editor and the
 * candidate form mark a bad field the same way.
 *
 * @param {Record<string, string>} errors
 * @param {string} errorKey
 * @returns {string} Empty when the field is fine, so it concatenates cleanly.
 */
export const errorBorder = (errors, errorKey) =>
  errors?.[errorKey] ? " border-destructive" : "";
