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
 * Dialog for verifying one of the caller's contact emails (email OTP). The
 * address is fixed to the picked row — verification proves from inside the
 * account that the caller controls that mailbox, which is what unlocks the
 * address as a sign-in method. On success it closes and asks the parent to
 * refresh the settings view.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {string} props.email - the address to verify.
 * @param {() => (void|Promise<void>)} props.onVerified - called after a verified code.
 */
const VerifyEmailDialog = ({ open, onOpenChange, email, onVerified }) => {
  const handleVerified = async () => {
    onOpenChange(false);
    toast.success("Email verified. You can now use it to sign in.");
    await onVerified?.();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Verify email</DialogTitle>
          <DialogDescription>
            Verify {email} to use it for signing in.
          </DialogDescription>
        </DialogHeader>
        <OtpVerifyForm
          idPrefix="verify-email"
          initialEmail={email}
          lockEmail
          onVerified={handleVerified}
        />
      </DialogContent>
    </Dialog>
  );
};

export default VerifyEmailDialog;
