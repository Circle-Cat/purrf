import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * DiscardChangesDialog
 *
 * Asks before unsaved holiday calendar edits are thrown away, by changing the
 * year or leaving the tab. Closing it any other way keeps the edits.
 *
 * @param {{isOpen: boolean, onStay: () => void, onDiscard: () => void}} props
 * @returns {JSX.Element}
 */
const DiscardChangesDialog = ({ isOpen, onStay, onDiscard }) => (
  <Dialog open={isOpen} onOpenChange={(open) => !open && onStay()}>
    <DialogContent className="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>Discard unsaved changes?</DialogTitle>
      </DialogHeader>
      <p className="text-sm text-muted-foreground">
        This year has changes that are not saved. Leaving now throws them away.
      </p>
      <DialogFooter>
        <Button variant="outline" onClick={onStay}>
          Keep editing
        </Button>
        <Button onClick={onDiscard}>Discard changes</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);

export default DiscardChangesDialog;
