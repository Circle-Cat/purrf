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
 * Dialog for adding a new email to the caller's account. Adding and
 * verifying are a single flow: the backend only ever records an address once
 * its OTP has been confirmed, so a successfully verified email is already
 * usable for contact and sign-in — there is no separate unverified state to
 * clean up afterwards. On success it closes and asks the parent to refresh
 * the settings view.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {() => (void|Promise<void>)} props.onAdded - called after a successful add.
 */
const AddEmailDialog = ({ open, onOpenChange, onAdded }) => {
  const handleVerified = async () => {
    onOpenChange(false);
    toast.success("Email added and verified.");
    await onAdded?.();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add an email</DialogTitle>
          <DialogDescription>
            We'll send a verification code to the address; entering it adds the
            email to your account, ready for contact and sign-in.
          </DialogDescription>
        </DialogHeader>
        {open && (
          <OtpVerifyForm idPrefix="add-email" onVerified={handleVerified} />
        )}
      </DialogContent>
    </Dialog>
  );
};

export default AddEmailDialog;
