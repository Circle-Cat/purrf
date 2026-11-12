import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { conversations } from "@/pages/Inbox/inboxDisplay";

/**
 * DeleteThreadsDialog
 *
 * Confirms deleting `count` Unsorted threads. Deleting removes them from
 * Purrf only; the mail stays in Gmail.
 *
 * @param {{count: number, pending: boolean, onConfirm: Function,
 *   onCancel: Function}} props
 * @returns {JSX.Element}
 */
const DeleteThreadsDialog = ({ count, pending, onConfirm, onCancel }) => (
  <Dialog open onOpenChange={(open) => !open && !pending && onCancel()}>
    <DialogContent className="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>Delete {conversations(count)}?</DialogTitle>
        <DialogDescription>
          They are removed from Purrf. The original emails stay in the Gmail
          mailbox.
        </DialogDescription>
      </DialogHeader>
      <DialogFooter>
        <Button variant="outline" disabled={pending} onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="destructive" disabled={pending} onClick={onConfirm}>
          Delete
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);

export default DeleteThreadsDialog;
