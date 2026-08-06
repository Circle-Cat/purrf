/**
 * The red line under a field that failed validation, and the matching border
 * for the control itself.
 *
 * Shared so every section of the posting editor reports a problem the same
 * way, and so the one element carrying `data-error-key` is the one
 * `PostingEditor` scrolls to — the anchor and the message cannot drift apart
 * because they are the same node. The matching border comes from
 * `errorBorder` in `postingValidation`, which is not a component module and
 * so can export a plain helper.
 *
 * @param {{errors: Record<string, string>, errorKey: string}} props
 */
const FieldError = ({ errors, errorKey }) =>
  errors?.[errorKey] ? (
    <span
      data-error-key={errorKey}
      className="mt-1 block text-xs text-destructive"
    >
      {errors[errorKey]}
    </span>
  ) : null;

export default FieldError;
