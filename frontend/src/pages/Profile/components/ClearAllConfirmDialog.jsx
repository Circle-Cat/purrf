import { useId } from "react";
import { Button } from "@/components/ui/button";

/**
 * Confirmation shown before a save that would leave a profile section with no
 * entries at all.
 *
 * Rendered as a plain overlay rather than through `@/components/ui/dialog`:
 * `DialogContent` hardcodes its backdrop at `z-50`, which the edit modal's own
 * `z-[1000]` backdrop would cover.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.open - Whether the confirmation is showing.
 * @param {string} props.sectionName - The section being cleared, lowercase, as
 *   it reads mid-sentence in the copy (e.g. "work experience").
 * @param {boolean} [props.isSaving] - Disables both buttons while the save runs.
 * @param {() => void} props.onConfirm - Go ahead with the save.
 * @param {() => void} props.onCancel - Dismiss and return to the edit modal.
 */
const ClearAllConfirmDialog = ({
  open,
  sectionName,
  isSaving = false,
  onConfirm,
  onCancel,
}) => {
  // Not derived from `sectionName`: a section reads as a phrase in the copy,
  // and an id cannot contain the space.
  const titleId = useId();

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[1100] flex h-full w-full items-center justify-center bg-black/40 backdrop-blur-[4px] animate-in fade-in duration-200">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="w-[90%] max-w-[440px] rounded-2xl border bg-background p-8 animate-in zoom-in-95 duration-200"
      >
        <h4 id={titleId} className="text-lg font-semibold">
          Remove all {sectionName}?
        </h4>
        <p className="mt-3 text-sm text-muted-foreground">
          This will remove all {sectionName} entries from your profile. You can
          add them back anytime.
        </p>
        <div className="mt-8 flex justify-end gap-3">
          <Button variant="outline" onClick={onCancel} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isSaving}>
            {isSaving ? "Removing..." : "Remove all"}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ClearAllConfirmDialog;
