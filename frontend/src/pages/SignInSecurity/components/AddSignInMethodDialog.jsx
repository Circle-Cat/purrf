import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import OtpVerifyForm from "@/components/common/OtpVerifyForm";

/**
 * Dialog for adding a sign-in method by verifying an email address (email OTP).
 * The verified address also becomes a contact email. On success it closes and
 * asks the parent to refresh the settings view.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {() => (void|Promise<void>)} props.onAdded - called after a verified add.
 */
const AddSignInMethodDialog = ({ open, onOpenChange, onAdded }) => {
  const handleVerified = async () => {
    onOpenChange(false);
    toast.success("Sign-in method added.");
    await onAdded?.();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add a sign-in method</DialogTitle>
          <DialogDescription>
            Verify an email address to use it for signing in.
          </DialogDescription>
        </DialogHeader>
        <OtpVerifyForm idPrefix="add-signin" onVerified={handleVerified} />
      </DialogContent>
    </Dialog>
  );
};

export default AddSignInMethodDialog;
